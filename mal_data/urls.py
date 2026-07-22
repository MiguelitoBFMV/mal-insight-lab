from django.urls import path

from .web import library as library_views
from .web import search as search_views
from .web import seasonal as seasonal_views
from .web import relations as relations_views
from .web import sync as sync_views
from .web import dashboard as dashboard_views
from .web import oauth as oauth_views

app_name = "mal_insights"


urlpatterns = [
    path("", dashboard_views.dashboard, name="dashboard"),

    path(
        "status/<str:status>/",
        library_views.anime_status_list,
        name="anime_status_list",
    ),
    path(
        "<int:mal_id>/relations/",
        relations_views.anime_relations_detail,
        name="anime_relations_detail",
    ),
    path(
        "sync/",
        sync_views.sync_anime_list_view,
        name="sync_anime_list",
    ),
    path(
        "<int:mal_id>/relations/sync/",
        relations_views.sync_anime_relations_view,
        name="sync_anime_relations",
    ),
    path(
        "search/",
        search_views.anime_search_view,
        name="anime_search",
    ),
    path(
        "search/rescue/",
        search_views.rescue_anime_from_search_view,
        name="rescue_anime_from_search",
    ),
    path(
        "seasonal/",
        seasonal_views.seasonal_board,
        name="seasonal_board",
    ),
    path(
        "seasonal/sync/",
        seasonal_views.sync_seasonal_board_view,
        name="sync_seasonal_board",
    ),
    path(
        "seasonal/add-to-plan/",
        seasonal_views.add_seasonal_to_plan_view,
        name="add_seasonal_to_plan",
    ),
    path(
    "oauth/mal/connect/",
    oauth_views.mal_oauth_connect,
    name="mal_oauth_connect",
    ),
    path(
        "oauth/mal/callback/",
        oauth_views.mal_oauth_callback,
        name="mal_oauth_callback",
    ),
]