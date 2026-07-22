from django.db import transaction
from django.utils import timezone

from games.models import Game
from games.services.igdb_client import IGDBClient
from games.services.igdb_normalizer import (
    normalize_game_payload,
)


IGDB_METADATA_FIELDS = (
    "igdb_id",
    "title",
    "summary",
    "cover_url",
    "artwork_url",
    "first_release_date",
    "igdb_main_story_hours",
    "genres",
    "platforms",
    "igdb_payload",
)


class IGDBImportError(Exception):
    """Base exception for local IGDB imports."""


class IGDBGameNotFoundError(IGDBImportError):
    """Raised when IGDB does not contain the requested game."""


class IGDBImportConflictError(IGDBImportError):
    """Raised when an IGDB game is already linked elsewhere."""


def apply_igdb_metadata(
    game,
    normalized_data,
):
    for field_name in IGDB_METADATA_FIELDS:
        setattr(
            game,
            field_name,
            normalized_data[field_name],
        )

    game.igdb_synced_at = timezone.now()

    return game


def import_game_from_igdb(
    igdb_id,
    *,
    target_game=None,
    client=None,
):
    client = client or IGDBClient()

    raw_game = client.get_game(
        igdb_id
    )

    if raw_game is None:
        raise IGDBGameNotFoundError(
            (
                "IGDB does not contain a game "
                f"with ID {igdb_id}."
            )
        )

    time_to_beat = (
        client.get_game_time_to_beat(
            igdb_id
        )
    )

    normalized_data = normalize_game_payload(
        raw_game,
        time_to_beat_payload=time_to_beat,
    )

    normalized_igdb_id = (
        normalized_data["igdb_id"]
    )

    with transaction.atomic():
        game_with_igdb_id = (
            Game.objects
            .select_for_update()
            .filter(
                igdb_id=normalized_igdb_id
            )
            .first()
        )

        if target_game is not None:
            if target_game.pk is None:
                raise IGDBImportError(
                    (
                        "A target game must already "
                        "exist in the database."
                    )
                )

            game = (
                Game.objects
                .select_for_update()
                .get(pk=target_game.pk)
            )

            if (
                game_with_igdb_id is not None
                and game_with_igdb_id.pk
                != game.pk
            ):
                raise IGDBImportConflictError(
                    (
                        "This IGDB game is already "
                        "linked to another local game."
                    )
                )

            created = False

        elif game_with_igdb_id is not None:
            game = game_with_igdb_id
            created = False

        else:
            game = Game()
            created = True

        apply_igdb_metadata(
            game,
            normalized_data,
        )

        game.save()

    return game, created


def refresh_game_from_igdb(
    game,
    *,
    client=None,
):
    if not game.igdb_id:
        raise IGDBImportError(
            (
                "This game is not linked "
                "to an IGDB record."
            )
        )

    return import_game_from_igdb(
        game.igdb_id,
        target_game=game,
        client=client,
    )