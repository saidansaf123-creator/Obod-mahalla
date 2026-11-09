import tempfile
from pathlib import Path
from types import SimpleNamespace

import openpyxl
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from .analysis import analyze
from .merge import categorize, clean_mahalla, merge, tps_in
from .models import District, Goal, GoalTask, Mahalla, Transformer
from .translit import fix_cyr, to_latin
from .views import build_payload


def fake_tp(**kw):
    base = dict(voltage_a=230, voltage_b=230, voltage_c=230, load_factor=0.3, pf=0.99,
                consumers_total=150, capacity_kva=400, daily_kwh=1500)
    base.update(kw)
    tp = SimpleNamespace(**base)
    tp.has_anomaly = tp.daily_kwh is not None and tp.daily_kwh <= 0
    return tp


class AnalysisTests(TestCase):
    def test_normal_tp_is_good(self):
        r = analyze(fake_tp())
        self.assertEqual(r.status, "good")
        self.assertEqual(r.issues, [])

    def test_low_voltage_and_anomaly(self):
        r = analyze(fake_tp(voltage_c=205, daily_kwh=-10))
        self.assertTrue(r.has("low_voltage"))
        self.assertTrue(r.has("anomaly"))

    def test_missing_values_and_low_pf(self):
        r = analyze(fake_tp(voltage_b=None, load_factor=None, pf=0.8))
        self.assertEqual(r.phases["Б"], "none")
        self.assertTrue(r.has("low_pf"))


class ParsingTests(TestCase):
    def test_names(self):
        self.assertEqual(to_latin("Бектемир"), "Bektemir")
        self.assertEqual(fix_cyr(" Конситутция "), "Конституция")
        self.assertEqual(clean_mahalla("“Янги сергели” МФЙ"), "Янги Сергели")
        self.assertEqual(clean_mahalla("Камолот маҳалласи "), "Камолот")

    def test_tp_numbers_and_categories(self):
        self.assertEqual(tps_in("ТП 1325 -17-уй паст кучланишли кабель"), ["1325"])
        self.assertEqual(tps_in("563-сонли трансформатор пунктини жорий таъмирлаш"), ["563"])
        self.assertEqual(categorize("563-сонли трансформатор пунктини жорий таъмирлаш"), "tp_current")
        self.assertEqual(categorize("ТП№3691 паст қувватли 400/10 трансформаторни 630/10 кВ трансформаторга алмаштириш"), "upgrade")
        self.assertEqual(categorize("Фидр Зеро ... юқори кучланишли кабелларни янгилаш"), "hv_cable")


class MergeAndPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_excel", "--no-excel", verbosity=0)

    def test_counts(self):
        self.assertEqual(District.objects.count(), 12)
        self.assertEqual(Mahalla.objects.count(), 120)
        self.assertEqual(Goal.objects.count(), 120)
        self.assertEqual(GoalTask.objects.count(), 535)
        self.assertEqual(Transformer.objects.filter(in_obod=True).count(), 205)

    def test_obod_names_corrected(self):
        tp = Transformer.objects.get(number="1821-1", in_obod=True)
        self.assertEqual(tp.obod_mahalla, "Конситутция")  # Обод файлидагидек
        self.assertEqual(tp.mahalla.name_cyr, "Лолазор")
        self.assertEqual(tp.district.name_cyr, "Миробод")

    def test_city_equals_sum_of_districts(self):
        p = build_payload()
        self.assertEqual(p["city"]["consumers"], sum(d["sys"]["consumers"] for d in p["districts"]))
        self.assertEqual(p["city"]["tp_count"], sum(d["sys"]["tp_count"] for d in p["districts"]))
        self.assertAlmostEqual(p["program"]["budget"], sum(m["budget"] for m in p["mahallas"]), delta=1)

    def test_single_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn('id="app-data"', res.content.decode())
        self.assertEqual(self.client.get("/api/").status_code, 404)

    def test_excel_export(self):
        from .export import export_workbook
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.xlsx"
            export_workbook(path, merge(settings.DATA_DIR))
            wb = openpyxl.load_workbook(path)
            self.assertEqual(wb.sheetnames, ["Маълумот", "Туманлар", "Маҳаллалар", "ТП лар", "Дастур ишлари", "Тузатишлар"])
            self.assertEqual(wb["ТП лар"].max_row, 801 + 2)
            self.assertTrue(str(wb["Маҳаллалар"]["C2"].value).startswith("=COUNTIFS("))
