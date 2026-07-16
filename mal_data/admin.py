from django.contrib import admin
from .models import AnimeAiringData, AnimeEntry, AnimeRelation, AnimeSyncEvent, MangaEntry, ManualTrackedAnime


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

@admin.register(AnimeRelation)
class AnimeRelationAdmin(admin.ModelAdmin):
    list_display = (
        "source_title",
        "relation_source_type",
        "relation_type_formatted",
        "target_title",
        "target_local_list_status",
        "last_synced_at",
    )

    list_filter = (
        "relation_source_type",
        "relation_type",
        "target_local_list_status",
    )

    search_fields = (
        "source_title",
        "target_title",
        "source_mal_id",
        "target_mal_id",
    )

    readonly_fields = (
        "raw_data",
        "last_synced_at",
    )

@admin.register(AnimeSyncEvent)
class AnimeSyncEventAdmin(admin.ModelAdmin):
    list_display = (
        "title_snapshot",
        "event_type",
        "old_value",
        "new_value",
        "created_at",
    )
    list_filter = ("event_type", "created_at")
    search_fields = ("title_snapshot", "mal_id")

@admin.register(AnimeAiringData)
class AnimeAiringDataAdmin(admin.ModelAdmin):
    list_display = (
        "anime",
        "mal_id",
        "anilist_id",
        "anilist_status",
        "episodes_aired_estimated",
        "next_airing_episode",
        "next_airing_at",
        "last_synced_at",
    )
    list_filter = ("anilist_status", "last_synced_at")
    search_fields = ("anime__title", "mal_id", "anilist_id")
    readonly_fields = ("raw_data", "streaming_links", "streaming_episodes")

@admin.register(ManualTrackedAnime)
class ManualTrackedAnimeAdmin(admin.ModelAdmin):
    list_display = (
        "title_snapshot",
        "mal_id",
        "status",
        "episodes_watched",
        "score",
        "active",
        "updated_at",
    )
    list_filter = ("status", "active")
    search_fields = ("title_snapshot", "mal_id")