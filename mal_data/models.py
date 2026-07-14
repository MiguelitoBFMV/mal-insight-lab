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
    

class AnimeEntry(models.Model):
    # Datos base del anime en MAL
    mal_id = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
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