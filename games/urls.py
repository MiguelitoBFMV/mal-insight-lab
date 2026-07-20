from django.urls import path

from .web import dashboard as dashboard_views
from .web import library as library_views

app_name = "games"


urlpatterns = [
    path(
        "",
        dashboard_views.dashboard,
        name="dashboard",
    ),
    path(
        "library/",
        library_views.library,
        name="library",
    ),
]