from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.energy import goals
from apps.energy.export import export_workbook
from apps.energy.merge import CATEGORIES, RES, merge
from apps.energy.models import District, Goal, GoalTask, Mahalla, Transformer
from apps.energy.stats import group_by, health_status, summarize
from apps.energy.translit import to_latin

OUT_NAME = "Обод маҳалла — бирлаштирилган маълумотлар.xlsx"


def _slug(name):
    return slugify(name.replace("'", "").replace("ʻ", "")) or "nomsiz"


def _json(d):
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


class Command(BaseCommand):
    help = ("Уч манбани (Обод файли, тизим ҳисоботи, 2027 дастури) бирлаштириб базага юклайди "
            "ва бирлаштирилган Excel файлни яратади.")

    def add_arguments(self, parser):
        parser.add_argument("--no-excel", action="store_true", help="Excel файл яратилмасин")
        parser.add_argument("--out", default=str(settings.DATA_DIR / OUT_NAME))

    def handle(self, *args, no_excel=False, out=None, **opts):
        m = merge(settings.DATA_DIR)
        with transaction.atomic():
            self._load(m)
        for n in m.notes:
            self.stdout.write(self.style.WARNING(n))
        self.stdout.write(self.style.SUCCESS(
            f"Юкланди: {District.objects.count()} туман, {Mahalla.objects.count()} маҳалла, "
            f"{Transformer.objects.count()} ТП, {Goal.objects.count()} мақсад, {GoalTask.objects.count()} иш."))
        if not no_excel:
            export_workbook(out, m)
            self.stdout.write(self.style.SUCCESS(f"Excel: {out}"))

    def _load(self, m):
        District.objects.all().delete()
        system = group_by([t for t in m.trload if t.active], lambda t: t.res)
        dmap = {}
        for res, (cyr, lat) in RES.items():
            s = _json(summarize(system[res]))
            s["status"] = health_status(s["health"])
            dmap[res] = District.objects.create(
                name=lat, name_cyr=cyr, slug=_slug(lat), res_name=res, system_stats=s,
                budget_official=m.program_summary[res]["budget"], program=m.program_summary[res]["rows"])

        mmap, used = {}, set()
        for res, name in m.mahallas:
            slug = base = _slug(to_latin(name))
            k = 2
            while (res, slug) in used:
                slug, k = f"{base}-{k}", k + 1
            used.add((res, slug))
            mmap[(res, name)] = Mahalla.objects.create(district=dmap[res], name=to_latin(name),
                                                       name_cyr=name, slug=slug)

        Transformer.objects.bulk_create([
            Transformer(
                district=dmap[t.res], mahalla=mmap.get(t.mahalla_key), number=t.number,
                base_number=t.base_number, substation=t.substation, feeder=t.feeder, owner=t.owner,
                meter_no=t.meter_no, ct_ratio=t.ct_ratio, meter_state=t.meter_state,
                consumers_total=t.consumers_total, consumers_household=t.consumers_household,
                consumers_commercial=t.consumers_commercial, capacity_kva=t.capacity_kva,
                daily_kwh=t.daily_kwh, monthly_kwh=t.monthly_kwh, yearly_kwh=t.yearly_kwh,
                kva_total=t.kva_total, kva_yesterday=t.kva_yesterday, pf=t.pf,
                voltage_a=t.voltage_a, voltage_b=t.voltage_b, voltage_c=t.voltage_c,
                current_a=t.current_a, current_b=t.current_b, current_c=t.current_c,
                load_factor=t.load_factor, in_program=t.in_program, in_obod=t.in_obod,
                obod_district=t.obod_district, obod_mahalla=t.obod_mahalla,
            ) for t in m.tps
        ])

        works_by_m = group_by(m.works, lambda w: (w.res, w.mahalla))
        tps_by_m = group_by([t for t in m.tps if t.mahalla_key], lambda t: t.mahalla_key)
        for key, mah in mmap.items():
            ws = [{"kind": w.kind, "title": w.title, "quantity": w.quantity, "unit": w.unit,
                   "cost_mln": w.cost, "tps": ", ".join(w.tps)} for w in works_by_m[key]]
            g = Goal.objects.create(mahalla=mah, **goals.generate(mah.name_cyr, ws, tps_by_m.get(key, [])))
            GoalTask.objects.bulk_create(
                GoalTask(goal=g, order=i, icon=CATEGORIES[w["kind"]][1], kind=w["kind"], title=w["title"],
                         quantity=w["quantity"], unit=w["unit"][:60], cost_mln=w["cost_mln"], tps=w["tps"][:250])
                for i, w in enumerate(ws))
