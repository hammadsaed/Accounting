from django.urls import path

from . import views

app_name = "investments"

urlpatterns = [
    path("", views.investment_list, name="list"),
    path("export.csv", views.profit_export, name="profit_export"),
    path("new/", views.investment_create, name="create"),
    path("<int:pk>/", views.investment_detail, name="detail"),
    path("<int:pk>/export.csv", views.investment_profit_export, name="investment_profit_export"),
    path("<int:pk>/update/", views.investment_update, name="update"),
    path("<int:pk>/delete/", views.investment_delete, name="delete"),
    path("<int:pk>/profits/new/", views.profit_create, name="profit_create"),
    path("profits/<int:pk>/update/", views.profit_update, name="profit_update"),
    path("profits/<int:pk>/delete/", views.profit_delete, name="profit_delete"),
]
