"""Маълумотлар билан ишлаш: Excel'ни юклаш, ижро журнали, сайт ҳолати (версия ва «ўзгартирилмоқда»)."""
import os
import tempfile
from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from . import goals as goal_gen
from .models import DataFile, District, Goal, Mahalla, ProgressEntry, Section, SiteState, SourceInfo, Work
from .source import find_source, read
from .translit import to_latin

SECTION_FIELDS = [
    "row", "res", "substation", "feeder", "number", "base_number", "owner", "master", "consumers_total",
    "consumers_household", "consumers_commercial", "capacity_kva", "meter_no", "ct_ratio", "daily_kwh",
    "kva_yesterday", "kva_total", "pf", "pf_l1", "pf_l2", "pf_l3", "current_a", "current_b", "current_c",
    "voltage_a", "voltage_b", "voltage_c", "load_factor", "meter_state", "note",
]
ENTRY_FIELDS = ["lv_km", "hv_km", "tr_upgrade", "new_gktp", "grsh", "cost"]
FACT_OF = {k: "fact_" + k for k in ENTRY_FIELDS}


class SourceError(Exception):
    pass


# ---------------------------------------------------------------- Сайт ҳолати
def state():
    obj, _ = SiteState.objects.get_or_create(pk=1)
    return obj


def bump_version():
    s = state()
    s.version += 1
    s.busy_until, s.busy_reason, s.busy_by = None, "", ""
    s.save()
    return s.version


def lock(session_key, reason, seconds=25):
    s = state()
    s.busy_until = timezone.now() + timedelta(seconds=seconds)
    s.busy_reason, s.busy_by = reason[:200], session_key or ""
    s.save(update_fields=["busy_until", "busy_reason", "busy_by", "updated_at"])


def unlock(session_key=None):
    s = state()
    if session_key is None or s.busy_by == (session_key or ""):
        s.busy_until, s.busy_reason, s.busy_by = None, "", ""
        s.save(update_fields=["busy_until", "busy_reason", "busy_by", "updated_at"])


def state_json(session_key=None):
    s = state()
    busy = bool(s.busy_until and s.busy_until > timezone.now())
    return {"version": s.version, "busy": busy, "mine": busy and s.busy_by == (session_key or "-"),
            "reason": s.busy_reason if busy else "", "updated": timezone.localtime(s.updated_at).strftime("%d.%m.%Y %H:%M")}


# ---------------------------------------------------------------- Ижро журнали
def work_key(w):
    return w.text_file or w.text


def recompute(work):
    """Иш «амалда» қийматлари = журналдаги ёзувлар йиғиндиси."""
    agg = ProgressEntry.objects.filter(work=work).aggregate(**{k: Sum(k) for k in ENTRY_FIELDS})
    for k in ENTRY_FIELDS:
        setattr(work, FACT_OF[k], round(agg[k] or 0, 4))
    last = ProgressEntry.objects.filter(work=work).exclude(note="").first()
    work.fact_note = last.note if last else ""
    work.save(update_fields=list(FACT_OF.values()) + ["fact_note"])


def relink_entries():
    """Excel қайта юклангандан кейин журнал ёзувларини янги ишларга боғлаш."""
    works = list(Work.objects.select_related("district"))
    by_full = {(w.district.order, w.number, work_key(w)): w for w in works}
    by_text = {}
    for w in works:
        by_text.setdefault((w.district.order, work_key(w)), []).append(w)
    linked = orphan = 0
    for e in ProgressEntry.objects.all():
        w = by_full.get((e.district_order, e.number, e.work_key))
        if w is None:
            cand = by_text.get((e.district_order, e.work_key), [])
            w = cand[0] if len(cand) == 1 else None
        e.work = w
        if w:
            e.number = w.number
            linked += 1
        else:
            orphan += 1
        e.save(update_fields=["work", "number"])
    for w in works:
        recompute(w)
    return linked, orphan


def add_entry(work, date, values, note=""):
    e = ProgressEntry.objects.create(
        work=work, district_order=work.district.order, number=work.number, work_key=work_key(work),
        work_title=work.title[:300], date=date, note=note.strip(),
        **{k: max(0.0, float(values.get(k) or 0)) for k in ENTRY_FIELDS})
    recompute(work)
    return e


def remaining(work):
    plan = {k: getattr(work, k) or 0 for k in ENTRY_FIELDS}
    return {k: max(0.0, round(plan[k] - (getattr(work, FACT_OF[k]) or 0), 4)) for k in ENTRY_FIELDS}


# ---------------------------------------------------------------- Excel'ни юклаш
def current_source():
    """Охирги юкланган файл (базада) ёки data/ даги файл."""
    df = DataFile.objects.first()
    if df:
        fd, tmp = tempfile.mkstemp(suffix=".xlsx")
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(df.content))
        return tmp, df.name, True
    p = find_source(settings.DATA_DIR)
    return str(p), p.name, False


def parse_upload(content, name):
    """Юкланган файлни текшириш: формат мос бўлмаса SourceError."""
    fd, tmp = tempfile.mkstemp(suffix=".xlsx")
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    try:
        src = read(tmp)
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"Файлни ўқиб бўлмади: {exc}") from exc
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if not src.districts or not src.works:
        raise SourceError("Файл формати мос эмас: туман ва иш қаторлари топилмади "
                          "(«Манзилли дастур» шаклидаги файлни юкланг).")
    src.path = type(src.path)(name)
    return src


def summary(src):
    return {"districts": len(src.districts), "works": len(src.works),
            "mahallas": len({(w.district, w.mahalla) for w in src.works}),
            "sections": sum(len(w.sections) for w in src.works),
            "cost": round(sum((w.cost or 0) for w in src.works), 2)}


@transaction.atomic
def load(src):
    """Базани файл асосида тўлиқ янгилаш; журнал ёзувлари сақланади ва қайта боғланади."""
    SourceInfo.objects.all().delete()
    District.objects.all().delete()   # маҳалла, иш, секция ва мақсадлар ҳам ўчади (журнал қолади)
    SourceInfo.objects.create(
        file_name=src.path.name, sheet=src.sheet, title=src.title, subtitle=src.subtitle, notes=src.notes,
        file_totals=src.city_file_totals, issues=[], row_count=src.row_count)

    dmap = {}
    for d in src.districts:
        lat = to_latin(d.name)
        dmap[d.order] = District.objects.create(
            order=d.order, roman=d.roman, name=d.name, name_lat=lat,
            slug=slugify(lat.replace("'", "")) or f"d{d.order}", res_name=d.res, file_totals=d.file_totals)

    mmap = OrderedDict()
    for w in src.works:
        key = (w.district, w.mahalla)
        if key not in mmap:
            n = sum(1 for k in mmap if k[0] == w.district)
            mmap[key] = Mahalla.objects.create(district=dmap[w.district], order=n + 1, name=w.mahalla,
                                               name_lat=to_latin(w.mahalla))

    for w in src.works:
        m = mmap[(w.district, w.mahalla)]
        obj = Work.objects.create(
            district=dmap[w.district], mahalla=m, number=w.number, rows=w.rows, text=w.text, text_file=w.text_file,
            title=w.title, tp_ref=w.tp_ref, mahalla_group=w.mahalla_group, category=w.category,
            categories=w.categories, text_categories=w.text_categories, cable_spec=w.cable_spec,
            target_kva=w.target_kva, tp_mentions=w.tp_mentions, issues=[], lv_km=w.lv_km, hv_km=w.hv_km,
            tr_upgrade=w.tr_upgrade, new_gktp=w.new_gktp, grsh=w.grsh, cost=w.cost,
            km_total_file=w.km_total_file, tr_total_file=w.tr_total_file)
        Section.objects.bulk_create([
            Section(work=obj, district=obj.district, mahalla=m, **{k: getattr(s, k) for k in SECTION_FIELDS})
            for s in w.sections])

    for (dorder, name), m in mmap.items():
        ws = [w for w in src.works if w.district == dorder and w.mahalla == name]
        Goal.objects.create(mahalla=m, **goal_gen.generate(name, ws, [s for w in ws for s in w.sections]))

    linked, orphan = relink_entries()
    return dict(summary(src), entries_linked=linked, entries_orphan=orphan)
