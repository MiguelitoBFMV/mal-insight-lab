from django.contrib import admin

from games.models import (
    Franchise,
    Game,
    GameAccess,
    LibraryEntry,
    Playthrough,
    CompetitiveMode,
    CompetitiveRankRecord,
    CompetitiveRankTier,
)


class GameAccessInline(admin.TabularInline):
    model = GameAccess
    extra = 0
    fields = (
        "access_type",
        "platform_name",
        "store",
    )


class PlaythroughInline(admin.TabularInline):
    model = Playthrough
    extra = 0
    fields = (
        "number",
        "status",
        "text_language",
        "access",
        "progress_note",
        "hours_played",
        "started_on",
        "finished_on",
    )


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "display_order",
        "game_count",
        "updated_at",
    )
    search_fields = (
        "name",
        "description",
    )
    ordering = (
        "display_order",
        "name",
    )
    readonly_fields = (
        "slug",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Juegos")
    def game_count(self, obj):
        return obj.games.count()


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "franchise",
        "igdb_id",
        "first_release_date",
        "igdb_main_story_hours",
        "has_library_entry",
    )
    list_filter = (
        "franchise",
        "first_release_date",
    )
    search_fields = (
        "title",
        "title_japanese",
        "igdb_id",
    )
    list_select_related = (
        "franchise",
    )
    readonly_fields = (
        "slug",
        "created_at",
        "updated_at",
    )

    @admin.display(
        boolean=True,
        description="En biblioteca",
    )
    def has_library_entry(self, obj):
        return hasattr(obj, "library_entry")


@admin.register(LibraryEntry)
class LibraryEntryAdmin(admin.ModelAdmin):
    list_display = (
        "game",
        "status",
        "owned",
        "wishlisted",
        "has_platinum",
        "effective_hours",
        "updated_at",
    )
    list_filter = (
        "status",
        "has_platinum",
    )
    search_fields = (
        "game__title",
        "game__title_japanese",
        "notes",
    )
    list_select_related = (
        "game",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    inlines = (
        GameAccessInline,
        PlaythroughInline,
    )

    @admin.display(
        boolean=True,
        description="Propio",
    )
    def owned(self, obj):
        return obj.is_owned

    @admin.display(
        boolean=True,
        description="Wishlist",
    )
    def wishlisted(self, obj):
        return obj.is_wishlisted

    @admin.display(description="Horas efectivas")
    def effective_hours(self, obj):
        return obj.effective_main_story_hours or "—"


@admin.register(GameAccess)
class GameAccessAdmin(admin.ModelAdmin):
    list_display = (
        "library_entry",
        "access_type",
        "platform_name",
        "store",
    )
    list_filter = (
        "access_type",
        "platform_name",
        "store",
    )
    search_fields = (
        "library_entry__game__title",
    )
    list_select_related = (
        "library_entry__game",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Playthrough)
class PlaythroughAdmin(admin.ModelAdmin):
    list_display = (
        "library_entry",
        "number",
        "status",
        "text_language",
        "progress_note",
        "hours_played",
        "started_on",
        "finished_on",
    )
    list_filter = (
        "status",
        "text_language",
    )
    search_fields = (
        "library_entry__game__title",
        "progress_note",
        "notes",
    )
    list_select_related = (
        "library_entry__game",
        "access",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(CompetitiveMode)
class CompetitiveModeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "library_entry",
        "display_order",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "is_active",
    )
    search_fields = (
        "name",
        "library_entry__game__title",
    )
    ordering = (
        "library_entry__game__title",
        "display_order",
        "name",
    )


@admin.register(CompetitiveRankTier)
class CompetitiveRankTierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "library_entry",
        "rank_order",
        "uses_divisions",
        "division_count",
    )
    list_filter = (
        "uses_divisions",
    )
    search_fields = (
        "name",
        "library_entry__game__title",
    )
    ordering = (
        "library_entry__game__title",
        "rank_order",
        "name",
    )


@admin.register(CompetitiveRankRecord)
class CompetitiveRankRecordAdmin(admin.ModelAdmin):
    list_display = (
        "mode",
        "rank_tier",
        "division",
        "season",
        "recorded_at",
    )
    list_filter = (
        "mode",
        "rank_tier",
        "season",
    )
    search_fields = (
        "mode__name",
        "mode__library_entry__game__title",
        "rank_tier__name",
        "season",
    )
    date_hierarchy = "recorded_at"
    ordering = (
        "-recorded_at",
        "-pk",
    )


