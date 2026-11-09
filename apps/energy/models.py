from django.db import models

from .analysis import TPMetrics


class District(models.Model):
    name = models.CharField("Номи (лотин)", max_length=100, unique=True)
    name_cyr = models.CharField("Номи (кирилл)", max_length=100)
    slug = models.SlugField(unique=True)
    res_name = models.CharField("РЭС номи (тизимда)", max_length=100, blank=True)
    system_stats = models.JSONField("Тизим бўйича кўрсаткичлар (барча ТП)", default=dict)
    budget_official = models.FloatField("Дастур бюджети, 2-илова (млн сўм)", default=0)
    program = models.JSONField("Дастур йўналишлари (2-илова)", default=list)

    class Meta:
        ordering = ["name_cyr"]
        verbose_name = "Туман"
        verbose_name_plural = "Туманлар"

    def __str__(self):
        return self.name_cyr


class Mahalla(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="mahallas",
                                 verbose_name="Туман")
    name = models.CharField("Номи (лотин)", max_length=150)
    name_cyr = models.CharField("Номи (кирилл)", max_length=150)
    slug = models.SlugField()

    class Meta:
        ordering = ["name_cyr"]
        verbose_name = "Маҳалла"
        verbose_name_plural = "Маҳаллалар"
        constraints = [models.UniqueConstraint(fields=["district", "slug"], name="uniq_mahalla_slug")]

    def __str__(self):
        return self.name_cyr


class Transformer(TPMetrics, models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="transformers",
                                 verbose_name="Туман")
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="transformers", verbose_name="Маҳалла")
    number = models.CharField("ТП рақами", max_length=60)
    base_number = models.CharField("ТП асосий рақами", max_length=20, db_index=True)
    substation = models.CharField("Подстанция", max_length=120, blank=True)
    feeder = models.CharField("Фидер", max_length=120, blank=True)
    owner = models.CharField("Эгаси", max_length=30, blank=True)
    meter_no = models.CharField("Баланс ҳисоблагичи рақами", max_length=40, blank=True)
    ct_ratio = models.FloatField("Ток трансформатори коэффициенти", null=True, blank=True)
    meter_state = models.CharField("Ҳисоблагич ҳолати", max_length=60, blank=True)

    consumers_total = models.PositiveIntegerField("Жами истеъмолчилар", default=0)
    consumers_household = models.PositiveIntegerField("Аҳоли истеъмолчилар", default=0)
    consumers_commercial = models.PositiveIntegerField("Улгуржи истеъмолчилар", default=0)
    capacity_kva = models.PositiveIntegerField("Қуввати (кВА)")
    daily_kwh = models.FloatField("Ўртача кунлик истеъмол (кВт·соат)", null=True, blank=True)
    monthly_kwh = models.FloatField("Ўртача ойлик истеъмол (кВт·соат)", null=True, blank=True)
    yearly_kwh = models.FloatField("Ўртача йиллик истеъмол (кВт·соат)", null=True, blank=True)
    kva_total = models.FloatField("Жами қувват (кВА)", null=True, blank=True)
    kva_yesterday = models.FloatField("Кеча жами (кВА)", null=True, blank=True)
    pf = models.FloatField("Қувват коэффициенти (cos φ)", null=True, blank=True)
    voltage_a = models.FloatField("А фаза (В)", null=True, blank=True)
    voltage_b = models.FloatField("Б фаза (В)", null=True, blank=True)
    voltage_c = models.FloatField("С фаза (В)", null=True, blank=True)
    current_a = models.FloatField("А фаза токи (А)", null=True, blank=True)
    current_b = models.FloatField("Б фаза токи (А)", null=True, blank=True)
    current_c = models.FloatField("С фаза токи (А)", null=True, blank=True)
    load_factor = models.FloatField("Юкланганлик коэффициенти", null=True, blank=True)

    in_program = models.BooleanField("2027 дастурида бор", default=False)
    in_obod = models.BooleanField("«Обод маҳалла» файлида бор", default=False)
    obod_district = models.CharField("Эски туман (Обод файли)", max_length=100, blank=True)
    obod_mahalla = models.CharField("Эски маҳалла (Обод файли)", max_length=150, blank=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Трансформатор пункти"
        verbose_name_plural = "Трансформатор пунктлари"

    def __str__(self):
        return f"ТП-{self.number}"


class Goal(models.Model):
    PRIORITY_CHOICES = [("high", "Юқори"), ("medium", "Ўрта"), ("low", "Паст")]
    STATUS_CHOICES = [("planned", "Режалаштирилган"), ("in_progress", "Жараёнда"), ("done", "Бажарилди")]

    mahalla = models.OneToOneField(Mahalla, on_delete=models.CASCADE, related_name="goal",
                                   verbose_name="Маҳалла")
    title = models.CharField("Мақсад", max_length=250)
    summary = models.TextField("Изоҳ")
    priority = models.CharField("Устуворлик", max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField("Ҳолати", max_length=15, choices=STATUS_CHOICES, default="planned")
    year = models.PositiveSmallIntegerField("Йил", default=2027)
    budget_mln = models.FloatField("Бюджет (млн сўм)")
    beneficiaries = models.PositiveIntegerField("Фойда олувчи истеъмолчилар", default=0)
    effects = models.JSONField("Кутилаётган натижалар", default=list)

    class Meta:
        verbose_name = "Маҳалла мақсади"
        verbose_name_plural = "Маҳалла мақсадлари"

    def __str__(self):
        return f"{self.mahalla}: {self.title}"


class GoalTask(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="tasks")
    kind = models.CharField("Йўналиш", max_length=30)
    icon = models.CharField(max_length=30, default="circle-check")
    title = models.TextField("Иш номи")
    quantity = models.FloatField("Миқдори", null=True, blank=True)
    unit = models.CharField("Ўлчов бирлиги", max_length=60, blank=True)
    cost_mln = models.FloatField("Нархи (млн сўм)", default=0)
    tps = models.CharField("Тегишли ТП лар", max_length=250, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Иш"
        verbose_name_plural = "Ишлар"

    def __str__(self):
        return self.title[:80]
