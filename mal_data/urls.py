from django.urls import path

from . import views
from .web import library as library_views

app_name = "mal_insights"


urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path(
        "status/<str:status>/",
        library_views.anime_status_list,
        name="anime_status_list",
    ),
    path(
        "<int:mal_id>/relations/",
        views.anime_relations_detail,
        name="anime_relations_detail",
    ),
    path(
        "sync/",
        views.sync_anime_list_view,
        name="sync_anime_list",
    ),
    path(
        "<int:mal_id>/relations/sync/",
        views.sync_anime_relations_view,
        name="sync_anime_relations",
    ),
    path(
        "search/",
        views.anime_search_view,
        name="anime_search",
    ),
    path(
        "search/rescue/",
        views.rescue_anime_from_search_view,
        name="rescue_anime_from_search",
    ),
    path(
        "seasonal/",
        views.seasonal_board,
        name="seasonal_board",
    ),
    path(
        "seasonal/sync/",
        views.sync_seasonal_board_view,
        name="sync_seasonal_board",
    ),
    path(
        "seasonal/add-to-plan/",
        views.add_seasonal_to_plan_view,
        name="add_seasonal_to_plan",
    ),
]