from django.contrib.auth.decorators import (
    login_required,
)
from django.db.models import (
    Count,
    Exists,
    F,
    OuterRef,
    Prefetch,
    Q,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_POST,
)

from games.forms import FranchiseOwnerForm
from games.models import (
    Franchise,
    Game,
    GameAccess,
    LibraryEntry,
    Playthrough,
)


def _get_decorated_franchises(
    *,
    include_empty=False,
):
    library_games = (
        Game.objects
        .filter(
            library_entry__isnull=False,
        )
        .select_related(
            "library_entry",
        )
        .order_by(
            "-library_entry__updated_at",
            "title",
        )
    )

    franchise_queryset = (
        Franchise.objects
        .annotate(
            game_count=Count(
                "games",
                filter=Q(
                    games__library_entry__isnull=False,
                ),
                distinct=True,
            ),
            owned_count=Count(
                "games",
                filter=Q(
                    games__library_entry__accesses__access_type=(
                        GameAccess.AccessType.OWNED
                    ),
                ),
                distinct=True,
            ),
            completed_count=Count(
                "games",
                filter=(
                    Q(
                        games__library_entry__status=(
                            LibraryEntry.Status.COMPLETED
                        ),
                    )
                    | Q(
                        games__library_entry__playthroughs__status=(
                            Playthrough.Status.COMPLETED
                        ),
                    )
                ),
                distinct=True,
            ),
            platinum_count=Count(
                "games",
                filter=Q(
                    games__library_entry__has_platinum=True,
                ),
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                "games",
                queryset=library_games,
                to_attr="library_games",
            )
        )
    )

    if not include_empty:
        franchise_queryset = (
            franchise_queryset.filter(
                game_count__gt=0,
            )
        )

    franchises = list(
        franchise_queryset.order_by(
            "display_order",
            "name",
        )
    )

    for franchise in franchises:
        franchise.completion_percent = (
            round(
                franchise.completed_count
                / franchise.game_count
                * 100
            )
            if franchise.game_count
            else 0
        )

        status_priority = {
            LibraryEntry.Status.PLAYING: 0,
            LibraryEntry.Status.COMPLETED: 1,
            LibraryEntry.Status.PAUSED: 2,
            LibraryEntry.Status.MULTIPLAYER: 3,
            LibraryEntry.Status.PLAN_TO_PLAY: 4,
            LibraryEntry.Status.DROPPED: 5,
        }

        representative_labels = {
            LibraryEntry.Status.PLAYING: (
                "Currently Playing"
            ),
            LibraryEntry.Status.COMPLETED: (
                "Latest Completed"
            ),
            LibraryEntry.Status.PAUSED: (
                "Currently Paused"
            ),
            LibraryEntry.Status.MULTIPLAYER: (
                "Multiplayer"
            ),
            LibraryEntry.Status.PLAN_TO_PLAY: (
                "Plan to Play"
            ),
            LibraryEntry.Status.DROPPED: (
                "Previously Played"
            ),
        }

        if franchise.library_games:
            representative_game = min(
                franchise.library_games,
                key=lambda game: (
                    status_priority.get(
                        game.library_entry.status,
                        99,
                    )
                ),
            )

            representative_label = (
                representative_labels.get(
                    representative_game
                    .library_entry
                    .status,
                    "Featured Game",
                )
            )
        else:
            representative_game = None
            representative_label = ""

        franchise.representative_game = (
            representative_game
        )
        franchise.representative_label = (
            representative_label
        )

        if representative_game:
            franchise.representative_image_url = (
                representative_game.artwork_url
                or representative_game.cover_url
            )
        else:
            franchise.representative_image_url = ""

    return franchises


def _build_franchise_list_context(
    request,
    *,
    owner_form=None,
):
    franchises = _get_decorated_franchises(
        include_empty=(
            request.user.is_authenticated
        ),
    )

    if request.user.is_authenticated:
        owner_form = (
            owner_form
            or FranchiseOwnerForm()
        )
    else:
        owner_form = None

    return {
        "active_page": "franchises",
        "franchises": franchises,
        "franchise_count": len(franchises),
        "total_grouped_games": sum(
            franchise.game_count
            for franchise in franchises
        ),
        "owner_form": owner_form,
    }


def franchise_list(request):
    return render(
        request,
        "games/franchise_list.html",
        _build_franchise_list_context(
            request,
        ),
    )


@login_required
@require_POST
def create_franchise(request):
    owner_form = FranchiseOwnerForm(
        request.POST,
    )

    if owner_form.is_valid():
        franchise = owner_form.save()

        return redirect(
            franchise.get_absolute_url()
        )

    return render(
        request,
        "games/franchise_list.html",
        _build_franchise_list_context(
            request,
            owner_form=owner_form,
        ),
        status=200,
    )


def franchise_detail(
    request,
    slug,
    *,
    owner_form=None,
    delete_error=None,
):
    franchise = get_object_or_404(
        Franchise,
        slug=slug,
    )

    if request.user.is_authenticated:
        owner_form = (
            owner_form
            or FranchiseOwnerForm(
                instance=franchise,
                prefix="franchise",
            )
        )
    else:
        owner_form = None

    completed_playthroughs = (
        Playthrough.objects.filter(
            library_entry=OuterRef("pk"),
            status=Playthrough.Status.COMPLETED,
        )
    )

    sort_order = request.GET.get(
        "sort",
        "asc",
    ).strip()

    if sort_order not in {
        "asc",
        "desc",
    }:
        sort_order = "asc"

    if sort_order == "desc":
        release_order = F(
            "game__first_release_date"
        ).desc(
            nulls_last=True,
        )
    else:
        release_order = F(
            "game__first_release_date"
        ).asc(
            nulls_last=True,
        )

    entries = list(
        LibraryEntry.objects
        .filter(
            game__franchise=franchise,
        )
        .select_related(
            "game",
        )
        .prefetch_related(
            "accesses",
            "playthroughs",
        )
        .annotate(
            has_completed_history=Exists(
                completed_playthroughs
            ),
        )
        .order_by(
            release_order,
            "game__title",
        )
    )

    status_priority = {
        LibraryEntry.Status.PLAYING: 0,
        LibraryEntry.Status.COMPLETED: 1,
        LibraryEntry.Status.PAUSED: 2,
        LibraryEntry.Status.MULTIPLAYER: 3,
        LibraryEntry.Status.PLAN_TO_PLAY: 4,
        LibraryEntry.Status.DROPPED: 5,
    }

    representative_labels = {
        LibraryEntry.Status.PLAYING: (
            "Currently Playing"
        ),
        LibraryEntry.Status.COMPLETED: (
            "Latest Completed"
        ),
        LibraryEntry.Status.PAUSED: (
            "Currently Paused"
        ),
        LibraryEntry.Status.MULTIPLAYER: (
            "Multiplayer"
        ),
        LibraryEntry.Status.PLAN_TO_PLAY: (
            "Plan to Play"
        ),
        LibraryEntry.Status.DROPPED: (
            "Previously Played"
        ),
    }

    if entries:
        representative_entry = min(
            entries,
            key=lambda entry: (
                status_priority.get(
                    entry.status,
                    99,
                ),
                -(
                    entry.updated_at.timestamp()
                    if entry.updated_at
                    else 0
                ),
                entry.game.title.casefold(),
            ),
        )

        representative_game = (
            representative_entry.game
        )

        representative_image_url = (
            representative_game.artwork_url
            or representative_game.cover_url
        )

        representative_label = (
            representative_labels.get(
                representative_entry.status,
                "Featured Game",
            )
        )
    else:
        representative_entry = None
        representative_game = None
        representative_image_url = ""
        representative_label = ""

    total_games = len(entries)

    owned_count = sum(
        1
        for entry in entries
        if any(
            access.access_type
            == GameAccess.AccessType.OWNED
            for access in entry.accesses.all()
        )
    )

    completed_count = sum(
        1
        for entry in entries
        if (
            entry.status
            == LibraryEntry.Status.COMPLETED
            or entry.has_completed_history
        )
    )

    active_count = sum(
        1
        for entry in entries
        if entry.status
        in {
            LibraryEntry.Status.PLAYING,
            LibraryEntry.Status.PAUSED,
        }
    )

    plan_to_play_count = sum(
        1
        for entry in entries
        if entry.status
        == LibraryEntry.Status.PLAN_TO_PLAY
    )

    platinum_count = sum(
        1
        for entry in entries
        if entry.has_platinum
    )

    completion_percent = (
        round(
            completed_count
            / total_games
            * 100
        )
        if total_games
        else 0
    )

    context = {
        "active_page": "franchises",
        "franchise": franchise,
        "entries": entries,
        "total_games": total_games,
        "owned_count": owned_count,
        "completed_count": completed_count,
        "active_count": active_count,
        "plan_to_play_count": plan_to_play_count,
        "platinum_count": platinum_count,
        "completion_percent": completion_percent,
        "owner_form": owner_form,
        "representative_entry": (
            representative_entry
        ),
        "representative_game": (
            representative_game
        ),
        "representative_image_url": (
            representative_image_url
        ),
        "representative_label": (
            representative_label
        ),
        "sort_order": sort_order,
        "next_sort_order": (
            "desc"
            if sort_order == "asc"
            else "asc"
        ),
        "sort_action_label": (
            "Show newest first"
            if sort_order == "asc"
            else "Show oldest first"
        ),
        "delete_error": delete_error,
    }

    return render(
        request,
        "games/franchise_detail.html",
        context,
    )


@login_required
@require_POST
def update_franchise(
    request,
    slug,
):
    franchise = get_object_or_404(
        Franchise,
        slug=slug,
    )

    owner_form = FranchiseOwnerForm(
        request.POST,
        instance=franchise,
        prefix="franchise",
    )

    if owner_form.is_valid():
        franchise = owner_form.save()

        return redirect(
            franchise.get_absolute_url()
        )

    return franchise_detail(
        request,
        slug,
        owner_form=owner_form,
    )


@login_required
@require_POST
def delete_franchise(
    request,
    slug,
):
    franchise = get_object_or_404(
        Franchise,
        slug=slug,
    )

    if franchise.games.exists():
        return franchise_detail(
            request,
            slug,
            delete_error=(
                "A franchise with assigned games "
                "cannot be deleted. Move or remove "
                "its games first."
            ),
        )

    franchise.delete()

    return redirect(
        "games:franchise_list"
    )


