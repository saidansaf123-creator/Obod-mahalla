from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from .analysis import analyze, load_status
from .models import District, Mahalla, Section, Work
from .source import find_source, mentioned_tps, read, text_categories

SOURCE = find_source(settings.DATA_DIR)


class FakeTP:
    voltage_a = voltage_b = voltage_c = 230.0
    load_factor = 0.3
    consumers_total = 100
    capacity_kva = 400
    pf = 0.99
    daily_kwh = 1000.0
    has_anomaly = False


class AnalysisTests(TestCase):
    def test_load_categories(self):
        self.assertEqual(load_status(0.49), "good")
        self.assertEqual(load_status(0.55), "warn")
        self.assertEqual(load_status(0.60), "crit")

    def test_normal_tp(self):
        r = analyze(FakeTP())
        self.assertEqual(r.status, "good")
        self.assertEqual(r.issues, [])


class SourceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = read(SOURCE)

    def test_structure(self):
        self.assertEqual(len(self.src.districts), 12)
        self.assertEqual(self.src.row_count, 436)
        self.assertEqual(len(self.src.works), 389)
        self.assertEqual(sum(len(w.sections) for w in self.src.works), 110)

    def test_duplicate_rows_counted_once(self):
        """2690 ТП ишида 2 қатор (2 секция) — нарх бир марта олинади."""
        w = next(w for w in self.src.works if w.district == 1 and w.number == 2)
        self.assertEqual(len(w.rows), 2)
        self.assertEqual(w.cost, 771.92)
        self.assertEqual([s.number for s in w.sections], ["2690-1", "2690-2"])
        total = round(sum((w.cost or 0) for w in self.src.works), 2)
        self.assertEqual(total, 210507.55)
        self.assertEqual(self.src.city_file_totals["cost"], 218836.3)

    def test_district_file_totals(self):
        """Такрорсиз қатор бўлмаган Учтепа ва Бектемирда файл жами ҳисобга тенг."""
        for d in self.src.districts:
            if d.name in ("Учтепа", "Бектемир"):
                self.assertAlmostEqual(d.file_totals["cost"], d.calc_totals["cost"], places=2)

    def test_voltage_columns(self):
        """Сарлавҳада AJ=L2, AK=L1, AL=L3."""
        s = self.src.works[0].sections[0]
        self.assertEqual((s.voltage_a, s.voltage_b, s.voltage_c), (227.3, 228.5, 228.1))
        self.assertEqual(s.load_factor, 0.169)
        self.assertEqual(s.consumers_total, 217)

    def test_parsing_helpers(self):
        self.assertIn("grsh", text_categories("3 та ГРШ-0,4 кВ ни таъмирлаш"))
        self.assertEqual(mentioned_tps("ТП 3483 (I,II с) ва 2690-сонли"), ["3483", "2690"])

    def test_corrections(self):
        """Фақат тўғри маълумот: силжиган матн рақамлар бўйича, манфий истеъмол ва «630» олинмайди."""
        w = lambda d, n: next(x for x in self.src.works if x.district == d and x.number == n)
        self.assertIn("ГРШ", w(6, 18).text)                     # файлда бўлинган матн, рақамда 3 та ГРШ
        self.assertIn("1,92 км паст кучланишли", w(5, 24).text)  # файлда «ГРЩ таъмирлаш», рақамда 1,92 км
        self.assertEqual(w(11, 4).tp_ref, "")                    # «630» — ТП рақами эмас
        secs = [s for x in self.src.works for s in x.sections]
        self.assertFalse(any(s.daily_kwh is not None and s.daily_kwh <= 0 for s in secs))
        self.assertFalse(any(not s.has_data for s in secs))


class ImportAndPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_excel", verbosity=0)

    def test_counts(self):
        self.assertEqual(District.objects.count(), 12)
        self.assertEqual(Work.objects.count(), 389)
        self.assertEqual(Section.objects.count(), 110)
        self.assertGreater(Mahalla.objects.count(), 90)

    def test_facts_preserved_on_reimport(self):
        from datetime import date
        from . import services
        w = Work.objects.select_related("district").get(district__order=1, number=1)
        services.add_entry(w, date(2026, 11, 10), {"cost": 100})
        call_command("import_excel", verbosity=0)
        self.assertEqual(Work.objects.get(district__order=1, number=1).fact_cost, 100)

    def test_page_and_export(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="app-data"')
        x = self.client.get("/export.xlsx")
        self.assertEqual(x.status_code, 200)
        self.assertTrue(x.content.startswith(b"PK"))
        self.assertEqual(self.client.get("/api/").status_code, 404)


class AdminPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_excel", verbosity=0)

    def login(self, client=None, password="6613"):
        c = client or self.client
        return c.post("/panel/login", data={"password": password}, content_type="application/json")

    def test_password_required(self):
        w = Work.objects.first()
        r = self.client.post("/panel/entry", data={"work": w.id, "date": "2026-11-10", "cost": 5},
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.login(password="0000").status_code, 403)
        self.assertEqual(self.login().status_code, 200)

    def test_entry_updates_facts_and_version(self):
        from .models import ProgressEntry
        from . import services
        self.login()
        w = Work.objects.get(district__order=1, number=2)        # 771,92 млн, 0,45+0,45 км, 1 ГКТП
        v0 = services.state().version
        r = self.client.post("/panel/entry", data={"work": w.id, "date": "2026-11-10", "lv_km": 0.2, "cost": 100,
                                                   "note": "биринчи қадам"}, content_type="application/json")
        self.assertTrue(r.json()["ok"])
        w.refresh_from_db()
        self.assertEqual((w.fact_lv_km, w.fact_cost), (0.2, 100))
        self.assertGreater(services.state().version, v0)
        data = self.client.get("/api/data").json()["data"]
        self.assertEqual(data["city"]["fact"]["cost"], 100)
        # «қолганини бажарилди»
        self.client.post("/panel/entry", data={"work": w.id, "date": "2026-11-11", "complete": True},
                         content_type="application/json")
        w.refresh_from_db()
        self.assertAlmostEqual(w.fact_cost, 771.92)
        self.assertEqual(w.fact_new_gktp, 1)
        # ўчириш
        e = ProgressEntry.objects.filter(work=w).order_by("created_at").first()
        self.client.post(f"/panel/entry/{e.id}/delete")
        w.refresh_from_db()
        self.assertAlmostEqual(w.fact_cost, 671.92)

    def test_busy_visible_to_others(self):
        from django.test import Client
        self.login()
        self.client.post("/panel/lock", data={"reason": "тест"}, content_type="application/json")
        other = Client()
        st = other.get("/api/state").json()
        self.assertTrue(st["busy"])
        self.assertFalse(st["admin"])
        self.client.post("/panel/unlock")
        self.assertFalse(other.get("/api/state").json()["busy"])

    def test_upload_keeps_journal(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.login()
        w = Work.objects.get(district__order=3, number=1)
        self.client.post("/panel/entry", data={"work": w.id, "date": "2026-11-10", "hv_km": 1, "cost": 50},
                         content_type="application/json")
        bad = SimpleUploadedFile("x.xlsx", b"not excel")
        self.assertFalse(self.client.post("/panel/upload", {"file": bad}).json()["ok"])
        self.assertEqual(Work.objects.count(), 389)               # нотўғри файл базани ўзгартирмайди
        good = SimpleUploadedFile("Обод_махалла_2027.xlsx", Path(SOURCE).read_bytes())
        r = self.client.post("/panel/upload", {"file": good}).json()
        self.assertTrue(r["ok"])
        self.assertEqual(r["entries_linked"], 1)
        w2 = Work.objects.get(district__order=3, number=1)
        self.assertNotEqual(w2.id, w.id)
        self.assertEqual(w2.fact_cost, 50)
