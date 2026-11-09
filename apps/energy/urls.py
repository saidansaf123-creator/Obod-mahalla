from django.urls import path

from . import views

app_name = "energy"

urlpatterns = [
    path("", views.app, name="app"),
]
