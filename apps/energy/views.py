"""Бир бетли интерфейс: барча маълумот саҳифага JSON кўринишида жойланади."""
from collections import defaultdict
from statistics import median

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from django.core.cache import cache

from . import services
from .models import District, Goal, ProgressEntry, Section, SourceInfo, Work
from .source import CATEGORIES, PLAN_FIELDS
from .stats import FACT_MAP, fact_totals, group_by, health_status, plan_totals, summarize


def _r(v, d=2):
    return round(v, d) if isinstance(v, float) else v


def _rd(dct, d=2):
    return {k: _r(v, d) for k, v in dct.items()}


def _tp_stats(secs):
    s = _rd(summarize(secs))
    s["status"] = health_status(s["health"]) if s.get("with_data") else "none"
    return s


def expected_after(works, sections_by_work):
    """Режадаги ишлар бажарилгандан кейинги ҳисобланган (тахминий) ҳолат.

    Трансформатор алмаштириш: J устунидаги сонича энг юкланган, қуввати янги қувватдан кичик секциялар
    янги қувватга (матндан, одатда 630 кВА) ўтказилади; юклама ўзгармайди деб олинади.
    Янги ГКТП: K × янги қувват қўшимча қувват захираси.
    """
    after = {}
    added, upgraded, gktp_kva = 0.0, 0, 0.0
    for w in works:
        target = w.target_kva or 630
        if w.tr_upgrade:
            cands = sorted([s for s in sections_by_work.get(w.id, []) if s.has_data and 0 < s.capacity_kva < target],
                           key=lambda s: -(s.load_factor or 0))
            for s in cands[:int(w.tr_upgrade)]:
                kva = s.kva_total or 0
                after[s.id] = {"cap": target, "lf": round(kva / target, 3), "work": w.id}
                added += target - s.capacity_kva
                upgraded += 1
        if w.new_gktp:
            gktp_kva += (w.new_gktp or 0) * target
    return after, {"added_kva": added, "upgraded": upgraded, "gktp_kva": gktp_kva, "total_kva": added + gktp_kva}


def unit_costs(works):
    """Бир бирлик иш нархи (фақат бир турдаги ҳажми бор ишлар бўйича)."""
    out = []
    for kind, (label, _icon, unit, field) in CATEGORIES.items():
        if not field:
            continue
        vals = []
        for w in works:
            if w.cost and (getattr(w, field) or 0) > 0 and len(w.categories) == 1:
                vals.append(w.cost / getattr(w, field))
        if vals:
            out.append({"kind": kind, "label": label, "unit": unit, "n": len(vals), "min": round(min(vals), 2),
                        "median": round(median(vals), 2), "max": round(max(vals), 2),
                        "avg": round(sum(vals) / len(vals), 2)})
    return out


def _cats(works):
    c = defaultdict(lambda: {"cost": 0.0, "count": 0})
    for w in works:
        c[w.category]["cost"] += w.cost or 0
        c[w.category]["count"] += 1
    return sorted(({"kind": k, "cost": round(v["cost"], 2), "count": v["count"]} for k, v in c.items()),
                  key=lambda x: -x["cost"])


def build_payload():
    works = list(Work.objects.select_related("district", "mahalla"))
    secs = list(Section.objects.select_related("work"))
    goals = list(Goal.objects.all())
    src = SourceInfo.objects.first()
    entries = list(ProgressEntry.objects.all())
    last_entry = {}
    for e in entries:                       # ёзувлар саналар бўйича камайиш тартибида
        if e.work_id and e.work_id not in last_entry:
            last_entry[e.work_id] = e.date.isoformat()
    sec_by_w = group_by(secs, lambda s: s.work_id)
    after, expected = expected_after(works, sec_by_w)
    w_by_d, w_by_m = group_by(works, lambda w: w.district_id), group_by(works, lambda w: w.mahalla_id)
    s_by_d, s_by_m = group_by(secs, lambda s: s.district_id), group_by(secs, lambda s: s.mahalla_id)
    goal_by_m = {g.mahalla_id: g for g in goals}

    districts, mahallas = [], []
    for d in District.objects.prefetch_related("mahallas"):
        ms = list(d.mahallas.all())
        dw = w_by_d[d.id]
        districts.append({
            "id": d.id, "slug": d.slug, "roman": d.roman, "name": d.name, "lat": d.name_lat, "res": d.res_name,
            "mahallas": [m.id for m in ms], "plan": plan_totals(dw), "fact": fact_totals(dw),
            "cats": _cats(dw), "tp": _tp_stats(s_by_d[d.id]),
        })
        for m in ms:
            mw = w_by_m[m.id]
            g = goal_by_m.get(m.id)
            mahallas.append({
                "id": m.id, "d": d.id, "name": m.name, "lat": m.name_lat, "plan": plan_totals(mw),
                "fact": fact_totals(mw), "works": [w.id for w in mw], "tps": [s.id for s in s_by_m[m.id]],
                "goal": g.id if g else None, "tp": _tp_stats(s_by_m[m.id]), "cats": _cats(mw),
            })

    work_items = [{
        "id": w.id, "d": w.district_id, "m": w.mahalla_id, "no": w.number, "rows": w.rows, "text": w.text,
        "title": w.title, "tp": w.tp_ref, "mg": w.mahalla_group, "cat": w.category, "cats": w.categories,
        "tcats": w.text_categories, "cable": w.cable_spec, "tkva": w.target_kva, "tpm": w.tp_mentions,
        "lv": w.lv_km, "hv": w.hv_km, "up": w.tr_upgrade, "gk": w.new_gktp, "gr": w.grsh,
        "cost": w.cost, "kmf": w.km_total_file, "trf": w.tr_total_file,
        "f": {k: getattr(w, FACT_MAP[k]) for k in FACT_MAP}, "fn": w.fact_note,
        "secs": [s.id for s in sec_by_w.get(w.id, [])], "upd": last_entry.get(w.id),
    } for w in works]

    tp_items = []
    for s in secs:
        r = s.report
        tp_items.append({
            "id": s.id, "w": s.work_id, "d": s.district_id, "m": s.mahalla_id, "row": s.row, "res": s.res,
            "ps": s.substation, "fd": s.feeder, "n": s.number, "base": s.base_number, "own": s.owner,
            "mst": s.master, "ct": s.consumers_total, "ch": s.consumers_household, "cc": s.consumers_commercial,
            "cap": s.capacity_kva, "mtr": s.meter_no, "kt": s.ct_ratio, "dk": s.daily_kwh, "mk": s.monthly_kwh,
            "yk": s.yearly_kwh, "kvay": s.kva_yesterday, "kva": s.kva_total, "pf": s.pf, "pf1": s.pf_l1,
            "pf2": s.pf_l2, "pf3": s.pf_l3, "ia": s.current_a, "ib": s.current_b, "ic": s.current_c,
            "va": s.voltage_a, "vb": s.voltage_b, "vc": s.voltage_c, "lf": s.load_factor, "st": s.meter_state,
            "note": s.note, "data": s.has_data,
            "score": r.score if s.has_data else None, "status": r.status if s.has_data else "none",
            "hs": r.health if s.has_data else "none", "imb": r.imbalance_pct, "ph": r.phases,
            "anomaly": s.has_anomaly, "actual": round(s.actual_kva, 1), "reserve": round(s.reserve_kva, 1),
            "peak": round(s.peak_pct), "kpc": _r(s.kwh_per_consumer_month, 1), "avgv": _r(s.avg_voltage, 1),
            "issues": [{"level": i.level, "title": i.title, "text": i.text, "advice": i.advice, "icon": i.icon}
                       for i in r.issues] if s.has_data else [],
            "after": after.get(s.id),
        })

    def goal_status(mid):
        f = fact_totals(w_by_m[mid])
        if w_by_m[mid] and f["done"] == len(w_by_m[mid]):
            return "done"
        return "in_progress" if any(f[k] for k in ("lv_km", "hv_km", "tr_upgrade", "new_gktp", "grsh", "cost")) else "planned"

    goal_items = [{"id": g.id, "m": g.mahalla_id, "title": g.title, "summary": g.summary, "priority": g.priority,
                   "status": goal_status(g.mahalla_id), "year": g.year, "budget": round(g.budget_mln, 2), "benef": g.beneficiaries,
                   "effects": g.effects} for g in goals]

    city = {"plan": plan_totals(works), "fact": fact_totals(works), "tp": _tp_stats(secs), "cats": _cats(works),
            "districts": len(districts), "mahallas": len(mahallas), "expected": _rd(expected, 1)}
    source = {
        "file": src.file_name if src else "", "sheet": src.sheet if src else "", "title": src.title if src else "",
        "subtitle": src.subtitle if src else "", "notes": src.notes if src else [], "rows": src.row_count if src else 0,
        "imported": timezone.localtime(src.imported_at).strftime("%d.%m.%Y %H:%M") if src else "",
    }
    categories = {k: {"label": v[0], "icon": v[1], "unit": v[2]} for k, v in CATEGORIES.items()}
    plan_fields = [{"key": k, "label": v[0], "unit": v[1]} for k, v in PLAN_FIELDS.items()]
    entry_items = [{"id": e.id, "w": e.work_id, "do": e.district_order, "no": e.number, "t": e.work_title,
                    "date": e.date.isoformat(), "lv": e.lv_km, "hv": e.hv_km, "up": e.tr_upgrade, "gk": e.new_gktp,
                    "gr": e.grsh, "cost": e.cost, "note": e.note,
                    "at": timezone.localtime(e.created_at).strftime("%d.%m.%Y %H:%M")} for e in entries]
    return {"city": city, "source": source, "categories": categories, "planFields": plan_fields, "entries": entry_items,
            "unitCosts": unit_costs(works), "districts": districts, "mahallas": mahallas, "works": work_items,
            "tps": tp_items, "goals": goal_items}


def cached_payload():
    """Маълумот версияси ўзгармагунча тайёр JSON қайта ишлатилади."""
    version = services.state().version
    key = f"payload:{version}"
    data = cache.get(key)
    if data is None:
        data = build_payload()
        cache.set(key, data, 3600)
    return version, data


def app(request):
    version, payload = cached_payload()
    meta = {"admin": bool(request.session.get("is_admin")), "version": version}
    response = render(request, "app.html", {"payload": payload, "meta": meta})
    response["Cache-Control"] = "no-cache, must-revalidate"
    return response


def export_xlsx(request):
    from .export import build_workbook

    data = build_workbook()
    response = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename*=UTF-8''Obod_mahalla_2027_tahlil.xlsx"
    return response
