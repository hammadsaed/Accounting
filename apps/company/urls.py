from django.urls import path

from . import views

app_name = "company"

urlpatterns = [
    path("", views.company_detail, name="detail"),
    path("edit/", views.company_edit, name="edit"),
    path("default-investment/", views.default_investment_update, name="default_investment_update"),
    path("movements/new/", views.movement_create, name="movement_create"),
]
