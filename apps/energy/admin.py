from django.contrib import admin

from .models import DataFile, District, Goal, Mahalla, ProgressEntry, Section, SiteState, SourceInfo, Work


@admin.register(SourceInfo)
class SourceInfoAdmin(admin.ModelAdmin):
    list_display = ["file_name", "sheet", "row_count", "imported_at"]
    readonly_fields = ["file_name", "sheet", "title", "subtitle", "notes", "file_totals", "row_count", "imported_at"]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["order", "roman", "name", "res_name"]
    search_fields = ["name", "name_lat"]


@admin.register(Mahalla)
class MahallaAdmin(admin.ModelAdmin):
    list_display = ["name", "district", "order"]
    list_filter = ["district"]
    search_fields = ["name", "name_lat"]


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ["number", "substation", "feeder", "capacity_kva", "consumers_total", "load_factor"]
    readonly_fields = fields
    can_delete = False


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    """Ижро (амалда) маълумотлари шу ерда киритилади — сайтдаги «Ижро» бўлими шундан олинади."""
    list_display = ["district", "number", "mahalla", "category", "lv_km", "hv_km", "tr_upgrade", "new_gktp",
                    "grsh", "cost", "fact_cost"]
    list_filter = ["district", "category"]
    search_fields = ["text", "mahalla__name", "tp_ref"]
    inlines = [SectionInline]
    readonly_fields = ["district", "mahalla", "number", "rows", "text", "text_file", "tp_ref", "category", "lv_km", "hv_km",
                       "tr_upgrade", "new_gktp", "grsh", "cost"]
    fieldsets = [
        ("Режа (файлдан)", {"fields": readonly_fields}),
        ("Амалда (ижро журнали йиғиндиси — сайтдаги админ панелда киритилади)",
         {"fields": ["fact_lv_km", "fact_hv_km", "fact_tr_upgrade", "fact_new_gktp", "fact_grsh", "fact_cost", "fact_note"]}),
    ]

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + ["fact_lv_km", "fact_hv_km", "fact_tr_upgrade", "fact_new_gktp", "fact_grsh",
                                       "fact_cost", "fact_note"]


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["number", "district", "mahalla", "substation", "capacity_kva", "consumers_total", "load_factor"]
    list_filter = ["district"]
    search_fields = ["number", "substation", "feeder", "meter_no"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["mahalla", "title", "priority", "status", "budget_mln", "year"]
    list_filter = ["priority", "status", "mahalla__district"]
    list_editable = ["status"]


@admin.register(ProgressEntry)
class ProgressEntryAdmin(admin.ModelAdmin):
    list_display = ["date", "district_order", "number", "work_title", "lv_km", "hv_km", "tr_upgrade", "new_gktp",
                    "grsh", "cost", "created_at"]
    list_filter = ["date", "district_order"]
    search_fields = ["work_title", "note"]


@admin.register(DataFile)
class DataFileAdmin(admin.ModelAdmin):
    list_display = ["name", "size", "uploaded_at"]
    exclude = ["content"]
    readonly_fields = ["name", "size", "summary", "uploaded_at"]


@admin.register(SiteState)
class SiteStateAdmin(admin.ModelAdmin):
    list_display = ["version", "busy_until", "busy_reason", "updated_at"]
