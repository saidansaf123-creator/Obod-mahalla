from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.app, name="app"),
    path("export.xlsx", views.export_xlsx, name="export"),
    path("api/state", api.site_state, name="api-state"),
    path("api/data", api.site_data, name="api-data"),
    path("panel/login", api.login),
    path("panel/logout", api.logout),
    path("panel/lock", api.lock),
    path("panel/unlock", api.unlock),
    path("panel/entry", api.add_entry),
    path("panel/entry/<int:pk>/delete", api.delete_entry),
    path("panel/upload", api.upload),
    path("panel/uploads", api.uploads),
]
