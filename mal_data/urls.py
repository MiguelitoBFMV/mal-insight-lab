from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("anime/status/<str:status>/", views.anime_status_list, name="anime_status_list"),
    path("anime/<int:mal_id>/relations/", views.anime_relations_detail, name="anime_relations_detail"),
    path("anime/sync/", views.sync_anime_list_view, name="sync_anime_list"),
    path("anime/<int:mal_id>/relations/sync/", views.sync_anime_relations_view, name="sync_anime_relations"),
    path("anime/search/", views.anime_search_view, name="anime_search"),
    path("anime/search/rescue/", views.rescue_anime_from_search_view, name="rescue_anime_from_search"),
    path("anime/seasonal/", views.seasonal_board, name="seasonal_board"),
    path("anime/seasonal/add-to-plan/", views.add_seasonal_to_plan_view, name="add_seasonal_to_plan"),
]