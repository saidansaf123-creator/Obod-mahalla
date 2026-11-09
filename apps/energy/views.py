"""Бир бетли интерфейс: барча маълумот саҳифага JSON кўринишида жойланади."""
from collections import defaultdict

from django.shortcuts import render

from .merge import CATEGORIES
from .models import District, Goal, Transformer
from .stats import combine, group_by, health_status, summarize


def _r(v, d=2):
    return round(v, d) if isinstance(v, float) else v


def _stats(tps):
    s = {k: _r(v) for k, v in summarize(tps).items()}
    s["status"] = health_status(s["health"]) if s.get("tp_count") else "none"
    return s


def build_payload():
    tps = list(Transformer.objects.select_related("district", "mahalla"))
    goals = list(Goal.objects.select_related("mahalla").prefetch_related("tasks"))
    by_m = group_by([t for t in tps if t.mahalla_id], lambda t: t.mahalla_id)
    by_d = group_by(tps, lambda t: t.district_id)
    goal_by_m = {g.mahalla_id: g for g in goals}

    districts, mahallas = [], []
    for d in District.objects.prefetch_related("mahallas").order_by("name_cyr"):
        ms = sorted(d.mahallas.all(), key=lambda x: x.name_cyr)
        dg = [goal_by_m[m.id] for m in ms if m.id in goal_by_m]
        sys_stats = dict(d.system_stats)
        districts.append({
            "id": d.id, "slug": d.slug, "name": d.name_cyr, "lat": d.name, "res": d.res_name,
            "sys": {k: _r(v) for k, v in sys_stats.items()},
            "proj": _stats(by_d[d.id]),
            "mahallas": [m.id for m in ms],
            "budget": round(sum(g.budget_mln for g in dg), 1),
            "budget_official": round(d.budget_official, 1),
            "works": sum(len(g.tasks.all()) for g in dg),
            "prog_tps": sum(1 for t in by_d[d.id] if t.in_program),
            "unassigned": sum(1 for t in by_d[d.id] if not t.mahalla_id),
            "program": d.program,
        })
        for m in ms:
            mt = sorted(by_m[m.id], key=lambda t: t.number)
            g = goal_by_m.get(m.id)
            mahallas.append({
                "id": m.id, "d": d.id, "name": m.name_cyr, "lat": m.name,
                "stats": _stats(mt), "tps": [t.id for t in mt], "goal": g.id if g else None,
                "budget": round(g.budget_mln, 1) if g else 0, "works": len(g.tasks.all()) if g else 0,
            })

    tp_items = []
    for t in sorted(tps, key=lambda x: (x.district.name_cyr, x.mahalla.name_cyr if x.mahalla else "яяя", x.number)):
        r = t.report
        tp_items.append({
            "id": t.id, "m": t.mahalla_id, "d": t.district_id, "n": t.number,
            "ps": t.substation, "fd": t.feeder, "own": t.owner, "mtr": t.meter_no, "kt": t.ct_ratio,
            "st": t.meter_state, "cap": t.capacity_kva, "ct": t.consumers_total, "ch": t.consumers_household,
            "cc": t.consumers_commercial, "dk": t.daily_kwh, "mk": t.monthly_kwh, "yk": t.yearly_kwh,
            "va": t.voltage_a, "vb": t.voltage_b, "vc": t.voltage_c,
            "ia": t.current_a, "ib": t.current_b, "ic": t.current_c,
            "pf": t.pf, "kva": t.kva_total, "kvay": t.kva_yesterday, "lf": t.load_factor or 0,
            "score": r.score, "status": r.status, "hs": r.health, "imb": r.imbalance_pct, "ph": r.phases,
            "anomaly": t.has_anomaly, "actual": round(t.actual_kva, 1), "reserve": round(t.reserve_kva, 1),
            "peak": round(t.peak_pct), "kpc": _r(t.kwh_per_consumer_month, 1),
            "avgv": _r(t.avg_voltage, 1), "prog": t.in_program, "obod": t.in_obod,
            "od": t.obod_district, "om": t.obod_mahalla,
            "issues": [{"level": i.level, "title": i.title, "text": i.text, "advice": i.advice, "icon": i.icon}
                       for i in r.issues],
        })

    cat_cost = defaultdict(lambda: {"cost": 0.0, "count": 0})
    goal_items = []
    for g in goals:
        tasks = list(g.tasks.all())
        cats = defaultdict(lambda: {"cost": 0.0, "count": 0})
        for t in tasks:
            for bucket in (cats[t.kind], cat_cost[t.kind]):
                bucket["cost"] += t.cost_mln
                bucket["count"] += 1
        goal_items.append({
            "id": g.id, "m": g.mahalla_id, "title": g.title, "summary": g.summary,
            "priority": g.priority, "status": g.status, "year": g.year, "budget": round(g.budget_mln, 2),
            "benef": g.beneficiaries, "effects": g.effects,
            "tpn": len(by_m.get(g.mahalla_id, [])),
            "cats": sorted(({"kind": k, "cost": round(v["cost"], 2), "count": v["count"]} for k, v in cats.items()),
                           key=lambda x: -x["cost"]),
            "tasks": [{"icon": t.icon, "kind": t.kind, "title": t.title, "qty": t.quantity, "unit": t.unit,
                       "cost": t.cost_mln, "tps": t.tps} for t in tasks],
        })

    city = {k: _r(v) for k, v in combine([d["sys"] for d in districts]).items()}
    city["status"] = health_status(city["health"])
    program = {
        "mahallas": len(mahallas), "works": sum(len(g["tasks"]) for g in goal_items),
        "budget": round(sum(g["budget"] for g in goal_items), 1),
        "budget_official": round(sum(d["budget_official"] for d in districts), 1),
        "tps": sum(1 for t in tps if t.in_program), "obod": sum(1 for t in tps if t.in_obod),
        "unassigned": sum(1 for t in tps if not t.mahalla_id),
        "benef": sum(g["benef"] for g in goal_items),
        "cats": sorted(({"kind": k, "cost": round(v["cost"], 1), "count": v["count"]} for k, v in cat_cost.items()),
                       key=lambda x: -x["cost"]),
    }
    categories = {k: {"label": v[0], "icon": v[1]} for k, v in CATEGORIES.items()}
    # «Обод маҳалла» лойиҳасига кирган барча ТП лар (дастур + Обод файли) ва маҳаллаларнинг жами
    project = _stats(tps)
    mtotal = _stats([t for t in tps if t.mahalla_id])
    return {"city": city, "project": project, "mtotal": mtotal, "program": program, "categories": categories, "districts": districts,
            "mahallas": mahallas, "tps": tp_items, "goals": goal_items}


def app(request):
    response = render(request, "app.html", {"payload": build_payload()})
    # Саҳифа ҳар сафар янгидан олинсин (маълумот ва скрипт версиялари мос бўлиши учун)
    response["Cache-Control"] = "no-cache, must-revalidate"
    return response
