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