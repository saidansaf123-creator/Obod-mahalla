from django.contrib import admin

from .models import District, Goal, GoalTask, Mahalla, Transformer


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["name_cyr", "name", "res_name", "budget_official"]
    search_fields = ["name", "name_cyr"]


class TransformerInline(admin.TabularInline):
    model = Transformer
    extra = 0
    fields = ["number", "capacity_kva", "consumers_total", "load_factor", "daily_kwh"]


@admin.register(Mahalla)
class MahallaAdmin(admin.ModelAdmin):
    list_display = ["name_cyr", "district", "name"]
    list_filter = ["district"]
    search_fields = ["name", "name_cyr"]
    inlines = [TransformerInline]


@admin.register(Transformer)
class TransformerAdmin(admin.ModelAdmin):
    list_display = ["number", "district", "mahalla", "capacity_kva", "consumers_total", "load_factor",
                    "voltage_a", "voltage_b", "voltage_c", "daily_kwh", "in_program", "in_obod"]
    list_filter = ["district", "in_program", "in_obod", "capacity_kva"]
    search_fields = ["number", "mahalla__name_cyr", "substation", "feeder"]
    list_select_related = ["district", "mahalla"]


class GoalTaskInline(admin.TabularInline):
    model = GoalTask
    extra = 0
    fields = ["order", "kind", "title", "quantity", "unit", "cost_mln", "tps"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["mahalla", "title", "priority", "status", "budget_mln", "year"]
    list_filter = ["priority", "status", "mahalla__district"]
    list_editable = ["status"]
    search_fields = ["title", "mahalla__name_cyr"]
    inlines = [GoalTaskInline]
