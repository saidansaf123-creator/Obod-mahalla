"""Админ панели ва сайт ҳолати учун JSON манзиллари."""
import json
import time
from datetime import date as date_cls
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import DataFile, ProgressEntry, Work
from .views import cached_payload

MAX_UPLOAD = 15 * 1024 * 1024
MAX_ATTEMPTS, LOCK_SECONDS = 5, 60


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def _err(msg, status=400):
    return JsonResponse({"ok": False, "error": msg}, status=status)


def admin_required(view):
    @wraps(view)
    def wrapper(request, *a, **kw):
        if not request.session.get("is_admin"):
            return _err("Аввал паролни киритинг.", 403)
        return view(request, *a, **kw)
    return wrapper


# ---------------------------------------------------------------- ҳамма учун
@require_GET
def site_state(request):
    data = services.state_json(request.session.session_key)
    data["admin"] = bool(request.session.get("is_admin"))
    return JsonResponse(data)


@require_GET
def site_data(request):
    version, payload = cached_payload()
    return JsonResponse({"version": version, "data": payload})


# ---------------------------------------------------------------- кириш
@require_POST
def login(request):
    s = request.session
    now = time.time()
    if s.get("login_block_until", 0) > now:
        return _err(f"Кўп марта нотўғри киритилди. {int(s['login_block_until'] - now)} сониядан кейин уриниб кўринг.", 429)
    if str(_body(request).get("password", "")).strip() == settings.ADMIN_PANEL_PASSWORD:
        s.cycle_key()
        s["is_admin"] = True
        s["login_attempts"] = 0
        return JsonResponse({"ok": True})
    s["login_attempts"] = s.get("login_attempts", 0) + 1
    if s["login_attempts"] >= MAX_ATTEMPTS:
        s["login_block_until"], s["login_attempts"] = now + LOCK_SECONDS, 0
    return _err("Парол нотўғри.", 403)


@require_POST
def logout(request):
    services.unlock(request.session.session_key)
    request.session.pop("is_admin", None)
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------- «ўзгартирилмоқда» белгиси
@require_POST
@admin_required
def lock(request):
    services.lock(request.session.session_key, _body(request).get("reason") or "Маълумот киритилмоқда")
    return JsonResponse({"ok": True})


@require_POST
@admin_required
def unlock(request):
    services.unlock(request.session.session_key)
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------- ижро журнали
def _parse_date(v):
    try:
        d = date_cls.fromisoformat(str(v))
    except ValueError:
        return None
    return d if d <= date_cls.today() else None


@require_POST
@admin_required
def add_entry(request):
    b = _body(request)
    try:
        work = Work.objects.select_related("district").get(pk=int(b.get("work")))
    except (Work.DoesNotExist, TypeError, ValueError):
        return _err("Иш топилмади.")
    d = _parse_date(b.get("date"))
    if not d:
        return _err("Сана нотўғри (келажак санаси бўлмайди).")
    vals = {}
    for k in services.ENTRY_FIELDS:
        try:
            v = float(str(b.get(k) or 0).replace(",", "."))
        except ValueError:
            return _err("Қийматлар рақам бўлиши керак.")
        if v < 0:
            return _err("Манфий қиймат киритиб бўлмайди.")
        vals[k] = v
    if b.get("complete"):
        vals = services.remaining(work)
    if not any(vals.values()) and not str(b.get("note", "")).strip():
        return _err("Камида битта қиймат ёки изоҳ киритинг.")
    e = services.add_entry(work, d, vals, str(b.get("note", ""))[:1000])
    version = services.bump_version()
    return JsonResponse({"ok": True, "id": e.id, "version": version})


@require_POST
@admin_required
def delete_entry(request, pk):
    try:
        e = ProgressEntry.objects.select_related("work").get(pk=pk)
    except ProgressEntry.DoesNotExist:
        return _err("Ёзув топилмади.", 404)
    w = e.work
    e.delete()
    if w:
        services.recompute(w)
    return JsonResponse({"ok": True, "version": services.bump_version()})


# ---------------------------------------------------------------- Excel юклаш
@require_POST
@admin_required
def upload(request):
    f = request.FILES.get("file")
    if not f:
        return _err("Файл танланмаган.")
    if not f.name.lower().endswith(".xlsx"):
        return _err("Фақат .xlsx файл юкланг.")
    if f.size > MAX_UPLOAD:
        return _err("Файл ҳажми 15 МБ дан катта.")
    key = request.session.session_key
    services.lock(key, "Янги Excel файл юкланмоқда", seconds=180)
    try:
        content = f.read()
        before = cached_payload()[1]["city"]["plan"]
        try:
            src = services.parse_upload(content, f.name)
        except services.SourceError as exc:
            services.unlock(key)
            return _err(str(exc))
        res = services.load(src)
        res["before"] = {"works": before.get("works"), "cost": before.get("cost")}
        DataFile.objects.create(name=f.name, content=content, size=len(content), summary=res)
        for old in DataFile.objects.all()[10:]:
            old.delete()
        res["version"] = services.bump_version()
    except Exception:
        services.unlock(key)
        raise
    return JsonResponse({"ok": True, **res})


@require_GET
@admin_required
def uploads(request):
    return JsonResponse({"items": [{"id": d.id, "name": d.name, "size": d.size, "summary": d.summary,
                                    "at": d.uploaded_at.isoformat()} for d in DataFile.objects.all()[:10]]})
