from django.urls import path

from .web import dashboard as dashboard_views
from .web import library as library_views
from .web import detail as detail_views

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
    path(
        "library/<slug:slug>/",
        detail_views.detail,
        name="detail",
    ),
    path(
        "library/<slug:slug>/update/",
        detail_views.update_entry,
        name="update_entry",
    ),
    path(
        (
            "library/<slug:slug>/"
            "playthroughs/<int:playthrough_id>/action/"
        ),
        detail_views.update_playthrough_state,
        name="update_playthrough_state",
    ),
    path(
        (
            "library/<slug:slug>/"
            "playthroughs/<int:playthrough_id>/update/"
        ),
        detail_views.update_playthrough,
        name="update_playthrough",
    ),
]