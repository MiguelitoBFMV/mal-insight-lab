from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("anime/status/<str:status>/", views.anime_status_list, name="anime_status_list"),
    path("anime/<int:mal_id>/relations/", views.anime_relations_detail, name="anime_relations_detail"),
    path(
        "anime/<int:mal_id>/relations/sync/",
        views.sync_anime_relations_view,
        name="sync_anime_relations",
    ),
]