from django.contrib.auth.decorators import (
    login_required,
)
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
)

from games.forms import (
    IGDBLinkExistingGameForm,
    IGDBNewGameImportForm,
)
from games.models import (
    Game,
    GameAccess,
    LibraryEntry,
)
from games.services.igdb_client import (
    IGDBClient,
    IGDBClientError,
)
from games.services.igdb_importer import (
    IGDBImportError,
    import_game_from_igdb,
    refresh_game_from_igdb,
)
from games.services.igdb_normalizer import (
    IGDBNormalizationError,
    build_igdb_image_url,
    extract_names,
    normalize_game_payload,
    unix_timestamp_to_date,
)   


def _build_search_result(payload):
    cover = payload.get("cover")

    if not isinstance(cover, dict):
        cover = {}

    try:
        igdb_id = int(payload.get("id"))
    except (TypeError, ValueError):
        igdb_id = None

    return {
        "igdb_id": igdb_id,
        "title": str(
            payload.get("name") or "Untitled Game"
        ).strip(),
        "slug": str(
            payload.get("slug") or ""
        ).strip(),
        "summary": str(
            payload.get("summary") or ""
        ).strip(),
        "release_date": unix_timestamp_to_date(
            payload.get("first_release_date")
        ),
        "cover_url": build_igdb_image_url(
            cover.get("image_id"),
            size="cover_big_2x",
        ),
        "genres": extract_names(
            payload.get("genres")
        ),
        "platforms": extract_names(
            payload.get("platforms")
        ),
    }


@login_required
def igdb_search(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    results = []
    error_message = ""

    if query:
        try:
            payloads = IGDBClient().search_games(
                query,
                limit=12,
            )
        except IGDBClientError as error:
            error_message = str(error)
        else:
            results = [
                _build_search_result(payload)
                for payload in payloads
            ]

            igdb_ids = [
                result["igdb_id"]
                for result in results
                if result["igdb_id"] is not None
            ]

            linked_games = {
                game.igdb_id: game
                for game in Game.objects.filter(
                    igdb_id__in=igdb_ids
                )
            }

            for result in results:
                result["local_game"] = (
                    linked_games.get(
                        result["igdb_id"]
                    )
                )

    context = {
        "active_page": "igdb_search",
        "query": query,
        "results": results,
        "result_count": len(results),
        "error_message": error_message,
    }

    return render(
        request,
        "games/igdb_search.html",
        context,
    )


def _load_import_preview(
    igdb_id,
):
    client = IGDBClient()

    raw_game = client.get_game(
        igdb_id
    )

    if raw_game is None:
        raise IGDBImportError(
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

    return normalize_game_payload(
        raw_game,
        time_to_beat_payload=time_to_beat,
    )


@login_required
@require_http_methods(
    [
        "GET",
        "POST",
    ]
)
def igdb_import(
    request,
    igdb_id,
):
    imported_game = (
        Game.objects
        .filter(
            igdb_id=igdb_id
        )
        .first()
    )

    if imported_game is not None:
        return redirect(
            imported_game.get_absolute_url()
        )

    available_games = (
        Game.objects
        .filter(
            igdb_id__isnull=True,
            library_entry__isnull=False,
        )
        .select_related(
            "library_entry"
        )
        .order_by(
            "title"
        )
    )

    import_action = request.POST.get(
        "import_action",
        "",
    )

    link_form = (
        IGDBLinkExistingGameForm(
            (
                request.POST
                if request.method == "POST"
                else None
            ),
            available_games=available_games,
            prefix="link",
        )
    )

    new_game_form = (
        IGDBNewGameImportForm(
            (
                request.POST
                if request.method == "POST"
                else None
            ),
            prefix="new",
            initial={
                "status": (
                    LibraryEntry.Status
                    .PLAN_TO_PLAY
                ),
                "access_type": (
                    GameAccess.AccessType
                    .OWNED
                ),
            },
        )
    )

    preview = None
    error_message = ""

    if request.method == "POST":
        try:
            if (
                import_action == "link"
                and link_form.is_valid()
            ):
                target_game = (
                    link_form.cleaned_data[
                        "existing_game"
                    ]
                )

                game, _created = (
                    import_game_from_igdb(
                        igdb_id,
                        target_game=target_game,
                    )
                )

                return redirect(
                    game.get_absolute_url()
                )

            if (
                import_action == "create"
                and new_game_form.is_valid()
            ):
                with transaction.atomic():
                    game, _created = (
                        import_game_from_igdb(
                            igdb_id
                        )
                    )

                    existing_entry = (
                        LibraryEntry.objects
                        .filter(game=game)
                        .first()
                    )

                    if existing_entry is not None:
                        return redirect(
                            game.get_absolute_url()
                        )

                    entry = LibraryEntry.objects.create(
                        game=game,
                        status=(
                            new_game_form
                            .cleaned_data[
                                "status"
                            ]
                        ),
                        has_platinum=(
                            new_game_form
                            .cleaned_data[
                                "has_platinum"
                            ]
                        ),
                        notes=(
                            new_game_form
                            .cleaned_data[
                                "notes"
                            ]
                        ),
                    )

                    GameAccess.objects.create(
                        library_entry=entry,
                        access_type=(
                            new_game_form
                            .cleaned_data[
                                "access_type"
                            ]
                        ),
                        platform_name=(
                            new_game_form
                            .cleaned_data[
                                "platform_name"
                            ]
                        ),
                        store=(
                            new_game_form
                            .cleaned_data[
                                "store"
                            ]
                        ),
                    )

                return redirect(
                    game.get_absolute_url()
                )

            if import_action not in {
                "link",
                "create",
            }:
                error_message = (
                    "Choose how this game "
                    "should be imported."
                )

        except (
            IGDBClientError,
            IGDBImportError,
            IGDBNormalizationError,
        ) as error:
            error_message = str(error)

    should_load_preview = (
        request.method == "GET"
        or (
            request.method == "POST"
            and not error_message
        )
    )

    if should_load_preview:
        try:
            preview = _load_import_preview(
                igdb_id
            )
        except (
            IGDBClientError,
            IGDBImportError,
            IGDBNormalizationError,
        ) as error:
            error_message = str(error)

    if (
        request.method == "GET"
        and preview is not None
    ):
        exact_local_match = (
            available_games
            .filter(
                title__iexact=preview["title"]
            )
            .first()
        )

        if exact_local_match is not None:
            link_form = (
                IGDBLinkExistingGameForm(
                    available_games=(
                        available_games
                    ),
                    initial={
                        "existing_game": (
                            exact_local_match
                        ),
                    },
                    prefix="link",
                )
            )

    context = {
        "active_page": "igdb_search",
        "igdb_id": igdb_id,
        "preview": preview,
        "link_form": link_form,
        "new_game_form": new_game_form,
        "available_game_count": (
            available_games.count()
        ),
        "error_message": error_message,
    }

    return render(
        request,
        "games/igdb_import.html",
        context,
    )


@login_required
@require_POST
def igdb_refresh(
    request,
    slug,
):
    game = get_object_or_404(
        Game,
        slug=slug,
    )

    if not game.igdb_id:
        return redirect(
            (
                f"{game.get_absolute_url()}"
                "?igdb_refresh=unlinked"
            )
        )

    try:
        refresh_game_from_igdb(
            game
        )
    except (
        IGDBClientError,
        IGDBImportError,
        IGDBNormalizationError,
    ):
        return redirect(
            (
                f"{game.get_absolute_url()}"
                "?igdb_refresh=error"
            )
        )

    return redirect(
        (
            f"{game.get_absolute_url()}"
            "?igdb_refresh=success"
        )
    )


