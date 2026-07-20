from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "MVS Tracker Administration"
admin.site.site_title = "MVS Tracker Admin"
admin.site.index_title = "Platform modules and data"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("core.urls")),
    path("anime/", include("mal_data.urls")),
    path("games/", include("games.urls")),
]