from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify
from django.urls import reverse


def generate_unique_slug(instance, value):
    """
    Generates a stable unique slug for Franchise and Game.

    Existing slugs are not regenerated when the visible name or title changes.
    """
    base_slug = slugify(value) or "item"
    candidate = base_slug
    model_class = type(instance)

    queryset = model_class.objects.all()

    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    suffix = 2

    while queryset.filter(slug=candidate).exists():
        candidate = f"{base_slug}-{suffix}"
        suffix += 1

    return candidate


class Franchise(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
    )
    slug = models.SlugField(
        max_length=170,
        unique=True,
        blank=True,
    )
    description = models.TextField(
        blank=True,
    )
    display_order = models.PositiveIntegerField(
        default=0,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "display_order",
            "name",
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(
                self,
                self.name,
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Game(models.Model):
    igdb_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    title = models.CharField(
        max_length=255,
    )
    title_japanese = models.CharField(
        max_length=255,
        blank=True,
    )
    slug = models.SlugField(
        max_length=280,
        unique=True,
        blank=True,
    )
    summary = models.TextField(
        blank=True,
    )
    cover_url = models.URLField(
        max_length=500,
        blank=True,
    )
    artwork_url = models.URLField(
        max_length=500,
        blank=True,
    )
    first_release_date = models.DateField(
        null=True,
        blank=True,
    )
    igdb_main_story_hours = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )
    genres = models.JSONField(
        default=list,
        blank=True,
    )

    platforms = models.JSONField(
        default=list,
        blank=True,
    )

    igdb_payload = models.JSONField(
        default=dict,
        blank=True,
    )

    igdb_synced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    franchise = models.ForeignKey(
        Franchise,
        related_name="games",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "title",
        ]
        indexes = [
            models.Index(
                fields=["title"],
                name="games_game_title_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(igdb_main_story_hours__isnull=True)
                    | Q(igdb_main_story_hours__gt=0)
                ),
                name="games_game_main_hours_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(
                self,
                self.title,
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse(
            "games:detail",
            kwargs={
                "slug": self.slug,
            },
        )


class LibraryEntry(models.Model):
    class Status(models.TextChoices):
        PLAYING = "playing", "Playing"
        PAUSED = "paused", "Paused"
        DROPPED = "dropped", "Dropped"
        PLAN_TO_PLAY = "plan_to_play", "Plan to Play"
        COMPLETED = "completed", "Completed"
        MULTIPLAYER = "multiplayer", "Multiplayer"

    game = models.OneToOneField(
        Game,
        related_name="library_entry",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        blank=True,
        default="",
        db_index=True,
    )
    has_platinum = models.BooleanField(
        default=False,
    )
    main_story_hours_override = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-updated_at",
            "game__title",
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(main_story_hours_override__isnull=True)
                    | Q(main_story_hours_override__gt=0)
                ),
                name="games_library_override_positive",
            ),
        ]

    @property
    def effective_main_story_hours(self):
        if self.main_story_hours_override is not None:
            return self.main_story_hours_override

        return self.game.igdb_main_story_hours

    @property
    def is_owned(self):
        return self.accesses.filter(
            access_type=GameAccess.AccessType.OWNED,
        ).exists()

    @property
    def is_wishlisted(self):
        return self.accesses.filter(
            access_type=GameAccess.AccessType.WISHLIST,
        ).exists()

    def __str__(self):
        return f"{self.game.title} · {self.get_status_display() or 'Sin estado'}"


class GameContent(models.Model):
    class ContentType(models.TextChoices):
        DLC = "dlc", "DLC"
        EXPANSION = "expansion", "Expansion"
        STANDALONE_EXPANSION = (
            "standalone_expansion",
            "Standalone Expansion",
        )
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PLAN_TO_PLAY = (
            "plan_to_play",
            "Plan to Play",
        )
        PLAYING = "playing", "Playing"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        DROPPED = "dropped", "Dropped"

    library_entry = models.ForeignKey(
        LibraryEntry,
        related_name="additional_contents",
        on_delete=models.CASCADE,
    )

    igdb_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    content_type = models.CharField(
        max_length=30,
        choices=ContentType.choices,
        default=ContentType.DLC,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLAN_TO_PLAY,
        db_index=True,
    )

    summary = models.TextField(
        blank=True,
    )

    cover_url = models.URLField(
        max_length=500,
        blank=True,
    )

    first_release_date = models.DateField(
        null=True,
        blank=True,
    )

    completed_on = models.DateField(
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    igdb_payload = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "title",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "library_entry",
                    "title",
                ],
                name="games_content_unique_title",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_on__isnull=True)
                    | Q(status="completed")
                ),
                name="games_content_completed_date_valid",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.completed_on
            and self.status
            != self.Status.COMPLETED
        ):
            raise ValidationError(
                {
                    "completed_on": (
                        "A completion date can only be "
                        "registered for completed content."
                    ),
                }
            )

    def __str__(self):
        return (
            f"{self.library_entry.game.title} · "
            f"{self.title}"
        )


class GameAccess(models.Model):
    class AccessType(models.TextChoices):
        OWNED = "owned", "Owned"
        WISHLIST = "wishlist", "Wishlist"

    class Platform(models.TextChoices):
        PC = "pc", "PC"
        PLAYSTATION_5 = "ps5", "PlayStation 5"
        NINTENDO_SWITCH_2 = "switch_2", "Nintendo Switch 2"
        OTHER = "other", "Other"

    class Store(models.TextChoices):
        STEAM = "steam", "Steam"
        EPIC_GAMES = "epic_games", "Epic Games Store"
        PLAYSTATION_STORE = (
            "playstation_store",
            "PlayStation Store",
        )
        NINTENDO_ESHOP = (
            "nintendo_eshop",
            "Nintendo eShop",
        )
        GOG = "gog", "GOG"
        OTHER = "other", "Otra"

    library_entry = models.ForeignKey(
        LibraryEntry,
        related_name="accesses",
        on_delete=models.CASCADE,
    )
    access_type = models.CharField(
        max_length=15,
        choices=AccessType.choices,
        db_index=True,
    )
    platform_name = models.CharField(
        "platform",
        max_length=30,
        choices=Platform.choices,
        db_index=True,
    )
    store = models.CharField(
        max_length=30,
        choices=Store.choices,
        blank=True,
        default="",
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "platform_name",
            "store",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "library_entry",
                    "access_type",
                    "platform_name",
                    "store",
                ],
                name="games_access_unique_location",
            ),
        ]

    def __str__(self):
        store = (
            f" · {self.get_store_display()}"
            if self.store
            else ""
        )

        return (
            f"{self.library_entry.game.title} · "
            f"{self.get_access_type_display()} · "
            f"{self.get_platform_name_display()}"
            f"{store}"
        )


class Playthrough(models.Model):
    class Status(models.TextChoices):
        PLAYING = "playing", "Playing"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        DROPPED = "dropped", "Dropped"

    class TextLanguage(models.TextChoices):
        JAPANESE = "ja", "Japanese"
        ENGLISH = "en", "English"
        SPANISH = "es", "Spanish"
        OTHER = "other", "Other"

    library_entry = models.ForeignKey(
        LibraryEntry,
        related_name="playthroughs",
        on_delete=models.CASCADE,
    )
    access = models.ForeignKey(
        GameAccess,
        related_name="playthroughs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PLAYING,
        db_index=True,
    )
    text_language = models.CharField(
        max_length=10,
        choices=TextLanguage.choices,
        db_index=True,
    )
    started_on = models.DateField(
        null=True,
        blank=True,
    )
    finished_on = models.DateField(
        null=True,
        blank=True,
    )
    progress_note = models.CharField(
        max_length=150,
        blank=True,
    )
    hours_played = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "library_entry",
            "number",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "library_entry",
                    "number",
                ],
                name="games_playthrough_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1),
                name="games_playthrough_number_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(hours_played__isnull=True)
                    | Q(hours_played__gt=0)
                ),
                name="games_playthrough_hours_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(started_on__isnull=True)
                    | Q(finished_on__isnull=True)
                    | Q(finished_on__gte=F("started_on"))
                ),
                name="games_playthrough_dates_valid",
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.started_on
            and self.finished_on
            and self.finished_on < self.started_on
        ):
            errors["finished_on"] = (
                "La fecha de término no puede ser anterior "
                "a la fecha de inicio."
            )

        if (
            self.access_id
            and self.library_entry_id
            and self.access.library_entry_id != self.library_entry_id
        ):
            errors["access"] = (
                "El acceso seleccionado debe pertenecer "
                "a la misma entrada de biblioteca."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.library_entry.game.title} · "
            f"Playthrough {self.number} · "
            f"{self.get_text_language_display()}"
        )