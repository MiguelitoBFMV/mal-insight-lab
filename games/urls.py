from django.urls import path

from .web import dashboard as dashboard_views


app_name = "games"


urlpatterns = [
    path(
        "",
        dashboard_views.dashboard,
        name="dashboard",
    ),
]