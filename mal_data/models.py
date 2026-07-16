from django.db import models
from django.utils import timezone


class MangaEntry(models.Model):
    # Datos base del manga en MAL
    mal_id = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    main_picture_url = models.URLField(blank=True, null=True)

    media_type = models.CharField(max_length=50, blank=True, null=True)
    publication_status = models.CharField(max_length=50, blank=True, null=True)

    num_volumes = models.PositiveIntegerField(default=0)
    num_chapters = models.PositiveIntegerField(default=0)

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Estado dentro de TU lista MAL
    list_status = models.CharField(max_length=50)
    score = models.PositiveIntegerField(default=0)

    num_volumes_read = models.PositiveIntegerField(default=0)
    num_chapters_read = models.PositiveIntegerField(default=0)

    is_rereading = models.BooleanField(default=False)
    updated_at_mal = models.DateTimeField(blank=True, null=True)

    # Guardamos el JSON original por seguridad/análisis futuro
    raw_data = models.JSONField(blank=True, null=True)

    # Control interno de sincronización
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def personal_status_label(self):
        if self.is_rereading:
            return "Rereading"

        status_labels = {
            "reading": "Reading",
            "completed": "Completed",
            "on_hold": "On hold",
            "dropped": "Dropped",
            "plan_to_read": "Plan to read",
        }

        return status_labels.get(self.list_status, self.list_status)

    class Meta:
        ordering = ["-updated_at_mal", "title"]

    def __str__(self):
        return f"{self.title} ({self.list_status})"
    

class AnimeEntry(models.Model):
    # Datos base del anime en MAL
    mal_id = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    title_japanese = models.CharField(max_length=255, blank=True, null=True)
    title_english = models.CharField(max_length=255, blank=True, null=True)
    main_picture_url = models.URLField(blank=True, null=True)

    media_type = models.CharField(max_length=50, blank=True, null=True)
    airing_status = models.CharField(max_length=50, blank=True, null=True)

    num_episodes = models.PositiveIntegerField(default=0)

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Estado dentro de TU lista MAL
    list_status = models.CharField(max_length=50)
    score = models.PositiveIntegerField(default=0)

    num_episodes_watched = models.PositiveIntegerField(default=0)
    is_rewatching = models.BooleanField(default=False)

    updated_at_mal = models.DateTimeField(blank=True, null=True)

    # Guardamos el JSON original por seguridad/análisis futuro
    raw_data = models.JSONField(blank=True, null=True)

    # Control interno de sincronización
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def display_title(self):
        if self.title_japanese:
            return f"{self.title} ({self.title_japanese})"

        return self.title

    @property
    def personal_status_label(self):
        if self.is_rewatching:
            return "Rewatching"

        status_labels = {
            "watching": "Watching",
            "completed": "Completed",
            "on_hold": "On hold",
            "dropped": "Dropped",
            "plan_to_watch": "Plan to watch",
        }

        return status_labels.get(self.list_status, self.list_status)

    class Meta:
        ordering = ["-updated_at_mal", "title"]

    def __str__(self):
        return f"{self.title} ({self.list_status})"
    
class AnimeRelation(models.Model):
    source_anime = models.ForeignKey(
        AnimeEntry,
        on_delete=models.CASCADE,
        related_name="relations",
        blank=True,
        null=True,
    )

    source_mal_id = models.PositiveIntegerField()
    source_title = models.CharField(max_length=255)

    target_mal_id = models.PositiveIntegerField()
    target_title = models.CharField(max_length=255)

    target_media_type = models.CharField(max_length=50, blank=True, null=True)
    target_status = models.CharField(max_length=50, blank=True, null=True)
    target_picture_url = models.URLField(blank=True, null=True)

    relation_type = models.CharField(max_length=100)
    relation_type_formatted = models.CharField(max_length=100, blank=True, null=True)

    # anime o manga
    relation_source_type = models.CharField(max_length=20)

    # Si el target existe en tu lista local, lo guardaremos después
    target_local_list_status = models.CharField(max_length=50, blank=True, null=True)

    raw_data = models.JSONField(blank=True, null=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def target_anime_entry(self):
        if self.relation_source_type != "anime":
            return None

        return AnimeEntry.objects.filter(mal_id=self.target_mal_id).first()

    @property
    def target_display_status(self):
        target = self.target_anime_entry

        if target:
            return target.personal_status_label

        if self.target_local_list_status:
            return self.target_local_list_status

        return "Not in local list"

    @property
    def target_display_media_type(self):
        target = self.target_anime_entry

        if target and target.media_type:
            return target.media_type

        return self.target_media_type or "-"

    @property
    def target_display_airing_status(self):
        target = self.target_anime_entry

        if target and target.airing_status:
            return target.airing_status

        return self.target_status or "-"

    @property
    def target_display_progress(self):
        target = self.target_anime_entry

        if not target:
            return "-"

        return f"{target.num_episodes_watched}/{target.num_episodes}"

    @property
    def target_display_score(self):
        target = self.target_anime_entry

        if not target:
            return "-"

        return target.score

    @property
    def target_display_title(self):
        target = self.target_anime_entry

        if target:
            return target.display_title

        return self.target_title

    class Meta:
        unique_together = (
            "source_mal_id",
            "target_mal_id",
            "relation_source_type",
            "relation_type",
        )
        ordering = ["source_title", "relation_source_type", "relation_type", "target_title"]

    def __str__(self):
        return f"{self.source_title} → {self.relation_type_formatted or self.relation_type} → {self.target_title}"
    
class AnimeSyncEvent(models.Model):
    EVENT_TYPES = [
        ("created", "Created"),
        ("status_changed", "Status changed"),
        ("episode_changed", "Episode changed"),
        ("score_changed", "Score changed"),
    ]

    anime = models.ForeignKey(
        AnimeEntry,
        on_delete=models.CASCADE,
        related_name="sync_events",
        blank=True,
        null=True,
    )
    mal_id = models.PositiveIntegerField()
    title_snapshot = models.CharField(max_length=255)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    old_value = models.CharField(max_length=100, blank=True, null=True)
    new_value = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title_snapshot} · {self.event_type}: {self.old_value} → {self.new_value}"


class AnimeAiringData(models.Model):
    anime = models.OneToOneField(
        AnimeEntry,
        on_delete=models.CASCADE,
        related_name="airing_data",
    )
    mal_id = models.PositiveIntegerField(unique=True)
    anilist_id = models.PositiveIntegerField(blank=True, null=True)

    title_romaji = models.CharField(max_length=255, blank=True, null=True)
    title_english = models.CharField(max_length=255, blank=True, null=True)
    title_native = models.CharField(max_length=255, blank=True, null=True)

    anilist_status = models.CharField(max_length=50, blank=True, null=True)
    anilist_episodes = models.PositiveIntegerField(default=0)

    next_airing_episode = models.PositiveIntegerField(blank=True, null=True)
    next_airing_at = models.DateTimeField(blank=True, null=True)
    time_until_airing_seconds = models.PositiveIntegerField(blank=True, null=True)

    episodes_aired_estimated = models.PositiveIntegerField(default=0)

    streaming_links = models.JSONField(default=list, blank=True)
    streaming_episodes = models.JSONField(default=list, blank=True)

    raw_data = models.JSONField(blank=True, null=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def pending_episodes_for_user(self):
        pending = self.episodes_aired_estimated - self.anime.num_episodes_watched
        return max(pending, 0)

    @property
    def has_episode_signal(self):
        return self.pending_episodes_for_user > 0

    def __str__(self):
        return f"{self.anime.title} · AniList airing data"
    
class ManualTrackedAnime(models.Model):
    STATUS_CHOICES = [
        ("watching", "Watching"),
        ("completed", "Completed"),
        ("on_hold", "On hold"),
        ("dropped", "Dropped"),
        ("plan_to_watch", "Plan to watch"),
    ]

    mal_id = models.PositiveIntegerField(unique=True)
    title_snapshot = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    episodes_watched = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    is_rewatching = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title_snapshot", "mal_id"]

    def __str__(self):
        title = self.title_snapshot or f"MAL ID {self.mal_id}"
        return f"{title} ({self.status})"