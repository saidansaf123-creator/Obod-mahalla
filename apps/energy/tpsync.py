"""ТП маълумотларини «Нагрузка» тизимидан (nagruzka.onrender.com) янгилаш.

Хавфсизлик:
- манзил фақат созламалардан олинади (фойдаланувчи манзил бера олмайди), фақат HTTPS, сертификат текширилади;
- юклаб олиш вақти ва ҳажми чекланган, файл ҳақиқатан xlsx ва керакли устунлар борлиги текширилади;
- қийматлар тури ва чегаралари текширилади, матнлар узунлиги қисқартирилади;
- фақат сайтда бор ТП секциялари янгиланади — янги ТП қўшилмайди, борлари ўчирилмайди;
- бир вақтда фақат битта янгилаш ишлайди.
"""
import io
import re
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse

import openpyxl
from django.conf import settings
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from . import services
from .models import Section, TpSync

MAX_BYTES = 40 * 1024 * 1024
TIMEOUT = 240                      # Render сервери уйқудан уйғониши учун вақт керак

# Файл устуни → (Section майдони, тур, мин, макс)
COLUMNS = {
    "Подстанция": ("substation", "str", 150),
    "Фидер": ("feeder", "str", 150),
    "ТП эгаси": ("owner", "str", 50),
    "Мастер Тр": ("master", "str", 100),
    "Нагрузка (%)": ("load_factor", "pct", 0, 400),
    "Қувват (kVA)": ("capacity_kva", "num", 0, 10000),
    "Жами (kVA)": ("kva_total", "num", 0, 20000),
    "Кеча жами (kVA)": ("kva_yesterday", "num", 0, 20000),
    "Ўрт. суткалик истеъмол (kWh)": ("daily_kwh", "kwh", -1e7, 1e7),
    "Ҳисоблагичлар (жами)": ("consumers_total", "int", 0, 100000),
    "Маиший": ("consumers_household", "int", 0, 100000),
    "Саноат": ("consumers_commercial", "int", 0, 100000),
    "Баланс ҳисоблагич": ("meter_no", "str", 50),
    "КТ коэффициенти": ("ct_ratio", "num", 0, 100000),
    "Ҳисоблагич ҳолати": ("meter_state", "str", 100),
    "cos φ": ("pf", "num", 0, 1.5),
    "cos φ L1": ("pf_l1", "num", 0, 1.5),
    "cos φ L2": ("pf_l2", "num", 0, 1.5),
    "cos φ L3": ("pf_l3", "num", 0, 1.5),
    "Ток L1 (А)": ("current_a", "num", 0, 100000),
    "Ток L2 (А)": ("current_b", "num", 0, 100000),
    "Ток L3 (А)": ("current_c", "num", 0, 100000),
    "Кучланиш L1 (В)": ("voltage_a", "num", 0, 1000),
    "Кучланиш L2 (В)": ("voltage_b", "num", 0, 1000),
    "Кучланиш L3 (В)": ("voltage_c", "num", 0, 1000),
    "Изоҳ": ("note", "str", 500),
}
KEY_RES, KEY_TP = "РЭС", "ТП рақами"
FIELDS = [v[0] for v in COLUMNS.values()]

NEG = "__neg__"                    # ҳисоблагич хатоси белгиси
_lock = threading.Lock()


class SyncError(Exception):
    pass


def source_url():
    url = settings.NAGRUZKA_EXPORT_URL
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise SyncError("Манзил созламаси нотўғри (фақат https).")
    return url


def download(url):
    # «Нагрузка» сервери аниқ Accept турида 406 қайтаради — шунинг учун */*; файл тури пастда текширилади
    req = urllib.request.Request(url, headers={"User-Agent": "ObodMahalla/1.0 (+tp-sync)", "Accept": "*/*"})
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)   # noqa: S310 — манзил созламалардан, фақат https
    except urllib.error.HTTPError as exc:
        raise SyncError(f"«Нагрузка» сервери хато қайтарди (код {exc.code}). Кейинроқ қайта уриниб кўринг.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SyncError("«Нагрузка» серверига уланиб бўлмади ёки жавоб жуда кечикди. Кейинроқ қайта уриниб кўринг.") from exc
    with resp as r:
        if r.status != 200:
            raise SyncError(f"Сервер жавоби: {r.status}")
        if urlparse(r.geturl()).hostname != urlparse(url).hostname:
            raise SyncError("Сервер бошқа манзилга йўналтирди — хавфсизлик учун тўхтатилди.")
        disp = r.headers.get("Content-Disposition", "")
        m = re.search(r'filename="?([^";]+)', disp)
        name = m.group(1) if m else "nagruzka.xlsx"
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SyncError("Файл жуда катта.")
    if not data.startswith(b"PK"):
        raise SyncError("Келган файл Excel (xlsx) эмас.")
    return re.sub(r"[^\w.\-]", "_", name)[:100], data


def _val(raw, kind, *lim):
    if kind == "str":
        return re.sub(r"\s+", " ", str(raw)).strip()[:lim[0]] if raw is not None else ""
    if raw is None or raw == "":
        return None
    try:
        v = float(str(raw).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None
    lo, hi = lim
    if not lo <= v <= hi:
        return None
    if kind == "pct":
        return round(v / 100, 4)
    if kind == "int":
        return int(v)
    if kind == "kwh":
        return v if v > 0 else NEG         # манфий/нол — ҳисоблагич хатоси (қиймат олиб ташланади)
    return v


def parse(data):
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise SyncError("Excel файлни ўқиб бўлмади.") from exc
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head = [str(h).strip() if h is not None else "" for h in next(rows, [])]
    need = [KEY_RES, KEY_TP] + list(COLUMNS)
    missing = [c for c in need if c not in head]
    if missing:
        raise SyncError("Файл шакли ўзгарган, устунлар топилмади: " + ", ".join(missing[:5]))
    idx = {c: head.index(c) for c in need}
    out = {}
    count = 0
    for row in rows:
        if not row or row[idx[KEY_TP]] in (None, ""):
            continue
        count += 1
        key = f"{_val(row[idx[KEY_RES]], 'str', 100)}|{_val(row[idx[KEY_TP]], 'str', 50)}"
        rec = {COLUMNS[c][0]: _val(row[idx[c]], *COLUMNS[c][1:]) for c in COLUMNS}
        out.setdefault(key, []).append(rec)
    wb.close()
    return count, out


def section_key(s):
    return f"{s.res}|{s.number}"


def _pick(cands, s):
    if len(cands) == 1:
        return cands[0]
    same = [c for c in cands if c.get("meter_no") == s.meter_no]
    return same[0] if len(same) == 1 else None


def apply(records):
    """records: {key: values} — фақат бор секцияларни янгилаш. Қайтаради: (ўзгарганлар сони, ўзгаришлар)."""
    changed, changes = 0, []
    for s in Section.objects.all():
        new = records.get(section_key(s))
        if not new:
            continue
        # Бўш катак — эски қиймат сақланади; фақат аниқ янги қийматлар ёзилади
        vals = {f: (None if new.get(f) == NEG else new.get(f)) for f in FIELDS
                if f in new and new[f] not in (None, "")}
        diff = {f: v for f, v in vals.items() if getattr(s, f) != v}
        if not diff:
            continue
        before = s.load_factor
        for f, v in diff.items():
            setattr(s, f, v)
        s.save(update_fields=list(diff))
        changed += 1
        changes.append({"n": s.number, "res": s.res, "fields": len(diff),
                        "lf_before": before, "lf_after": s.load_factor})
    return changed, changes


def reapply_latest():
    """Excel қайта юклангандан кейин охирги янгилашни қайта қўллаш (эски қийматларга қайтиб қолмаслик учун)."""
    last = TpSync.objects.filter(status="done").first()
    if last and last.data:
        apply(last.data)


def _run(job_id, session_key):
    close_old_connections()
    job = TpSync.objects.get(pk=job_id)

    def step(text, seconds=90):
        job.step = text
        job.save(update_fields=["step"])
        services.lock(session_key, f"ТП маълумотлари янгиланмоқда: {text}", seconds=seconds)

    try:
        step("«Нагрузка» тизимидан Excel файл юклаб олинмоқда (30–60 сония)…", seconds=TIMEOUT + 30)
        name, data = download(source_url())
        job.file_name = name
        step("Файл ўқилмоқда ва текширилмоқда…")
        total, parsed = parse(data)
        job.total_rows = total
        step("Сайтдаги ТП лар янгиланмоқда…")
        records, missing = {}, []
        for s in Section.objects.all():
            rec = _pick(parsed.get(section_key(s), []), s)
            if rec:
                records[section_key(s)] = rec
            else:
                missing.append(f"ТП-{s.number} ({s.res})")
        with transaction.atomic():
            changed, changes = apply(records)
            job.matched, job.changed, job.missing, job.data = len(records), changed, missing, records
            changes.sort(key=lambda c: -abs((c["lf_after"] or 0) - (c["lf_before"] or 0)))
            job.changes = changes[:200]
            job.status, job.step = "done", "Тайёр"
            job.message = (f"{len(records)} та ТП топилди, {changed} тасида маълумот ўзгарди"
                           + (f", {len(missing)} таси файлда йўқ (ўзгартирилмади)" if missing else "") + ".")
            job.finished_at = timezone.now()
            job.save()
        services.bump_version()          # бошқа фойдаланувчиларда сайт ўзи янгиланади
    except Exception as exc:  # noqa: BLE001
        job.status, job.finished_at = "error", timezone.now()
        job.message = str(exc) if isinstance(exc, SyncError) else f"Кутилмаган хато: {type(exc).__name__}. Кейинроқ қайта уриниб кўринг."
        job.step = "Хато"
        job.save()
        services.unlock(session_key)
    finally:
        _lock.release()
        connection.close()


def start(session_key):
    """Янгилашни фонда бошлаш. Аллақачон ишлаётган бўлса — шуни қайтаради."""
    running = TpSync.objects.filter(status="running").first()
    if running and (timezone.now() - running.started_at).total_seconds() < TIMEOUT + 120:
        return running, False
    if running:                       # осилиб қолган эски иш
        running.status, running.message = "error", "Вақт тугади."
        running.save()
    if not _lock.acquire(blocking=False):
        return TpSync.objects.filter(status="running").first(), False
    try:
        job = TpSync.objects.create(step="Бошланмоқда…")
    except Exception:
        _lock.release()
        raise
    threading.Thread(target=_run, args=(job.id, session_key), daemon=True).start()
    return job, True


def job_json(job):
    if not job:
        return None
    return {"id": job.id, "status": job.status, "step": job.step, "message": job.message, "file": job.file_name,
            "total": job.total_rows, "matched": job.matched, "changed": job.changed, "missing": job.missing,
            "changes": job.changes[:60], "started": timezone.localtime(job.started_at).strftime("%d.%m.%Y %H:%M:%S"),
            "finished": timezone.localtime(job.finished_at).strftime("%d.%m.%Y %H:%M:%S") if job.finished_at else ""}
