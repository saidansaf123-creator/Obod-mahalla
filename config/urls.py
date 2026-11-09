from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Обод маҳалла — бошқарув"
admin.site.site_title = "Обод маҳалла"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.energy.urls")),
]
