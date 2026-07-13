from django.contrib import admin
from .models import MangaEntry, AnimeEntry


@admin.register(MangaEntry)
class MangaEntryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "list_status",
        "score",
        "num_chapters_read",
        "num_chapters",
        "publication_status",
        "updated_at_mal",
    )

    list_filter = (
        "list_status",
        "publication_status",
        "media_type",
        "is_rereading",
    )

    search_fields = (
        "title",
        "mal_id",
    )

    readonly_fields = (
        "raw_data",
        "last_synced_at",
    )


@admin.register(AnimeEntry)
class AnimeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "list_status",
        "score",
        "num_episodes_watched",
        "num_episodes",
        "airing_status",
        "updated_at_mal",
    )

    list_filter = (
        "list_status",
        "airing_status",
        "media_type",
        "is_rewatching",
    )

    search_fields = (
        "title",
        "mal_id",
    )

    readonly_fields = (
        "raw_data",
        "last_synced_at",
    )