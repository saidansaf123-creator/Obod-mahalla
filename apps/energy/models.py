"""«Обод маҳалла 2027» маълумотлари — ягона манба: data/Обод_махалла_2027.xlsx."""
from django.db import models

from .analysis import TPMetrics


class SourceInfo(models.Model):
    """Охирги юкланган файл ҳақида маълумот ва текширув натижалари."""
    file_name = models.CharField("Файл", max_length=255)
    sheet = models.CharField("Варақ", max_length=255)
    title = models.TextField("Сарлавҳа")
    subtitle = models.CharField("Кичик сарлавҳа", max_length=255, blank=True)
    notes = models.JSONField("Изоҳлар", default=list)
    file_totals = models.JSONField("Файлдаги шаҳар жами", default=dict)
    issues = models.JSONField("Текширув натижалари", default=list)
    row_count = models.PositiveIntegerField("Иш қаторлари", default=0)
    imported_at = models.DateTimeField("Юкланган вақт", auto_now=True)

    class Meta:
        verbose_name = "Манба файл"
        verbose_name_plural = "Манба файл"

    def __str__(self):
        return self.file_name


class District(models.Model):
    order = models.PositiveSmallIntegerField("Тартиб")
    roman = models.CharField("Рақам", max_length=8)
    name = models.CharField("Номи", max_length=100)
    name_lat = models.CharField("Лотинча", max_length=100)
    slug = models.SlugField(unique=True)
    res_name = models.CharField("РЭС", max_length=100, blank=True)
    file_totals = models.JSONField("Файлдаги жами", default=dict)

    class Meta:
        ordering = ["order"]
        verbose_name = "Туман"
        verbose_name_plural = "Туманлар"

    def __str__(self):
        return self.name


class Mahalla(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="mahallas")
    order = models.PositiveSmallIntegerField("Тартиб", default=0)
    name = models.CharField("Номи", max_length=150)
    name_lat = models.CharField("Лотинча", max_length=150)

    class Meta:
        ordering = ["district__order", "order"]
        verbose_name = "Маҳалла"
        verbose_name_plural = "Маҳаллалар"

    def __str__(self):
        return f"{self.name} ({self.district})"


class Work(models.Model):
    """Манзилли дастурдаги битта иш (режа) ва унинг ижроси (амалда)."""
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="works")
    mahalla = models.ForeignKey(Mahalla, on_delete=models.CASCADE, related_name="works")
    number = models.PositiveIntegerField("№")
    rows = models.JSONField("Файл қаторлари", default=list)
    text = models.TextField("Бажариладиган ишлар")
    text_file = models.TextField("Файлдаги асл матн (тузатилган бўлса)", blank=True)
    title = models.TextField("Қисқа номи")
    tp_ref = models.CharField("ТП (C устуни)", max_length=50, blank=True)
    mahalla_group = models.CharField("Маҳалла (E устуни)", max_length=150, blank=True)
    category = models.CharField("Асосий тоифа", max_length=20)
    categories = models.JSONField("Тоифалар", default=list)
    text_categories = models.JSONField("Матн бўйича тоифалар", default=list)
    cable_spec = models.CharField("Кабел маркаси", max_length=60, blank=True)
    target_kva = models.PositiveIntegerField("Янги трансформатор қуввати", null=True, blank=True)
    tp_mentions = models.JSONField("Матнда тилга олинган ТП лар", default=list)
    issues = models.JSONField("Текширув", default=list)
    # Режа (файлдан)
    lv_km = models.FloatField("Паст кучланишли кабел, км", null=True, blank=True)
    hv_km = models.FloatField("Юқори кучланишли кабел, км", null=True, blank=True)
    tr_upgrade = models.FloatField("Трансформатор алмаштириш, дона", null=True, blank=True)
    new_gktp = models.FloatField("Янги ГКТП, дона", null=True, blank=True)
    grsh = models.FloatField("ГРШ модернизацияси, дона", null=True, blank=True)
    cost = models.FloatField("Зарур маблағ, млн сўм", null=True, blank=True)
    km_total_file = models.FloatField("F устуни (жами км)", null=True, blank=True)
    tr_total_file = models.FloatField("I устуни (жами трансформатор)", null=True, blank=True)
    # Амалда (ижро) — бошланғич қиймат 0, админ панелдан киритилади
    fact_lv_km = models.FloatField("Амалда: паст кучланишли кабел, км", default=0)
    fact_hv_km = models.FloatField("Амалда: юқори кучланишли кабел, км", default=0)
    fact_tr_upgrade = models.FloatField("Амалда: трансформатор алмаштириш", default=0)
    fact_new_gktp = models.FloatField("Амалда: янги ГКТП", default=0)
    fact_grsh = models.FloatField("Амалда: ГРШ", default=0)
    fact_cost = models.FloatField("Амалда: ўзлаштирилган маблағ, млн сўм", default=0)
    fact_note = models.TextField("Ижро изоҳи", blank=True)

    class Meta:
        ordering = ["district__order", "number"]
        verbose_name = "Иш"
        verbose_name_plural = "Ишлар"
        constraints = [models.UniqueConstraint(fields=["district", "number"], name="uniq_work_number")]

    def __str__(self):
        return f"{self.district} №{self.number}"

    @property
    def km_total(self):
        return (self.lv_km or 0) + (self.hv_km or 0)


class Section(TPMetrics, models.Model):
    """Ишга тегишли ТП секцияси (N–AO устунлари)."""
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="sections")
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="sections")
    mahalla = models.ForeignKey(Mahalla, on_delete=models.CASCADE, related_name="sections")
    row = models.PositiveIntegerField("Файл қатори")
    res = models.CharField("Название РЭС", max_length=100, blank=True)
    substation = models.CharField("Подстанция", max_length=150, blank=True)
    feeder = models.CharField("Фидер", max_length=150, blank=True)
    number = models.CharField("Номер ТП", max_length=50)
    base_number = models.CharField("ТП (C устуни)", max_length=50, blank=True)
    owner = models.CharField("Tr Владелец", max_length=50, blank=True)
    master = models.CharField("Мастер Тр", max_length=100, blank=True)
    consumers_total = models.PositiveIntegerField("Счётчиклар — всего", default=0)
    consumers_household = models.PositiveIntegerField("Бытовые", default=0)
    consumers_commercial = models.PositiveIntegerField("Промышленные", default=0)
    capacity_kva = models.FloatField("Мощность (kVA)", default=0)
    meter_no = models.CharField("Номер счетчика баланса", max_length=50, blank=True)
    ct_ratio = models.FloatField("Коэффициент КТ", null=True, blank=True)
    daily_kwh = models.FloatField("Среднесуточное потребление (kWh)", null=True, blank=True)
    kva_yesterday = models.FloatField("Вчера итого (kVA)", null=True, blank=True)
    kva_total = models.FloatField("Всего (kVA)", null=True, blank=True)
    pf = models.FloatField("PF", null=True, blank=True)
    pf_l1 = models.FloatField("PF L1", null=True, blank=True)
    pf_l2 = models.FloatField("PF L2", null=True, blank=True)
    pf_l3 = models.FloatField("PF L3", null=True, blank=True)
    current_a = models.FloatField("Средний ток L1 (A)", null=True, blank=True)
    current_b = models.FloatField("Средний ток L2 (A)", null=True, blank=True)
    current_c = models.FloatField("Средний ток L3 (A)", null=True, blank=True)
    voltage_a = models.FloatField("Среднее напряжение L1 (V)", null=True, blank=True)
    voltage_b = models.FloatField("Среднее напряжение L2 (V)", null=True, blank=True)
    voltage_c = models.FloatField("Среднее напряжение L3 (V)", null=True, blank=True)
    load_factor = models.FloatField("Нагрузки ТП", null=True, blank=True)
    meter_state = models.CharField("Состояние счетчика", max_length=100, blank=True)
    note = models.TextField("Примечание", blank=True)

    class Meta:
        ordering = ["district__order", "row"]
        verbose_name = "ТП секцияси"
        verbose_name_plural = "ТП секциялари"

    def __str__(self):
        return f"ТП-{self.number}"

    @property
    def monthly_kwh(self):
        return None if self.daily_kwh is None else self.daily_kwh * 30

    @property
    def yearly_kwh(self):
        return None if self.daily_kwh is None else self.daily_kwh * 365

    @property
    def has_data(self):
        return bool(self.capacity_kva) or self.daily_kwh is not None


class Goal(models.Model):
    mahalla = models.OneToOneField(Mahalla, on_delete=models.CASCADE, related_name="goal")
    title = models.CharField("Мақсад", max_length=300)
    summary = models.TextField("Тавсиф")
    priority = models.CharField("Устуворлик", max_length=10,
                                choices=[("high", "Юқори"), ("medium", "Ўрта"), ("low", "Паст")])
    status = models.CharField("Ҳолат", max_length=20, default="planned",
                              choices=[("planned", "Режалаштирилган"), ("in_progress", "Жараёнда"), ("done", "Бажарилди")])
    year = models.PositiveSmallIntegerField(default=2027)
    budget_mln = models.FloatField("Бюджет, млн сўм", default=0)
    beneficiaries = models.PositiveIntegerField("Истеъмолчилар", default=0)
    effects = models.JSONField("Кутилаётган натижалар", default=list)

    class Meta:
        verbose_name = "Мақсад"
        verbose_name_plural = "Мақсадлар"

    def __str__(self):
        return self.title


class ProgressEntry(models.Model):
    """Ижро журнали: админ ҳар куни киритадиган «амалда» ёзуви.

    Excel қайта юкланганда ишлар янгидан яратилади — ёзув (туман, №, асл матн) калити бўйича
    янги ишга қайта боғланади, шунинг учун журнал йўқолмайди.
    """
    work = models.ForeignKey(Work, on_delete=models.SET_NULL, null=True, blank=True, related_name="entries")
    district_order = models.PositiveSmallIntegerField("Туман тартиби")
    number = models.PositiveIntegerField("Иш №")
    work_key = models.TextField("Иш калити (файлдаги матн)")
    work_title = models.TextField("Иш номи", blank=True)
    date = models.DateField("Сана")
    lv_km = models.FloatField("Паст кучланишли кабел, км", default=0)
    hv_km = models.FloatField("Юқори кучланишли кабел, км", default=0)
    tr_upgrade = models.FloatField("Трансформатор алмаштириш", default=0)
    new_gktp = models.FloatField("Янги ГКТП", default=0)
    grsh = models.FloatField("ГРШ", default=0)
    cost = models.FloatField("Ўзлаштирилган маблағ, млн сўм", default=0)
    note = models.TextField("Изоҳ", blank=True)
    created_at = models.DateTimeField("Киритилган вақт", auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Ижро ёзуви"
        verbose_name_plural = "Ижро журнали"

    def __str__(self):
        return f"{self.date} · №{self.number}"


class DataFile(models.Model):
    """Админ юклаган Excel файллар (базада сақланади — сервер қайта ишга тушса ҳам йўқолмайди)."""
    name = models.CharField("Файл номи", max_length=255)
    content = models.BinaryField("Файл")
    size = models.PositiveIntegerField("Ҳажми", default=0)
    summary = models.JSONField("Натижа", default=dict)
    uploaded_at = models.DateTimeField("Юкланган вақт", auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Юкланган Excel"
        verbose_name_plural = "Юкланган Excel файллар"

    def __str__(self):
        return self.name


class SiteState(models.Model):
    """Сайт ҳолати: маълумот версияси ва «ўзгартирилмоқда» белгиси (бир қатор)."""
    version = models.PositiveIntegerField(default=1)
    busy_until = models.DateTimeField(null=True, blank=True)
    busy_reason = models.CharField(max_length=200, blank=True)
    busy_by = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Сайт ҳолати"
        verbose_name_plural = "Сайт ҳолати"
