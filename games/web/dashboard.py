from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import render

from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough,
)


def dashboard(request):

    completed_playthroughs = Playthrough.objects.filter(
        library_entry=OuterRef("pk"),
        status=Playthrough.Status.COMPLETED,
    )

    entries = (
        LibraryEntry.objects
        .select_related(
            "game",
            "game__franchise",
        )
        .prefetch_related(
            Prefetch(
                "accesses",
                queryset=GameAccess.objects.order_by(
                    "access_type",
                    "platform_name",
                    "store",
                ),
                to_attr="dashboard_accesses",
            ),
            Prefetch(
                "playthroughs",
                queryset=(
                    Playthrough.objects
                    .select_related("access")
                    .order_by("-number")
                ),
                to_attr="dashboard_playthroughs",
            ),
        )
        .annotate(
            has_completed_history=Exists(
                completed_playthroughs
            ),
        )
    )

    owned_entries = (
        LibraryEntry.objects
        .filter(
            accesses__access_type=GameAccess.AccessType.OWNED
        )
        .distinct()
    )

    owned_count = owned_entries.count()

    completable_owned_entries = owned_entries.exclude(
        status=LibraryEntry.Status.MULTIPLAYER
    )

    completable_owned_count = (
        completable_owned_entries.count()
    )

    wishlist_count = (
        LibraryEntry.objects
        .filter(
            accesses__access_type=(
                GameAccess.AccessType.WISHLIST
            )
        )
        .distinct()
        .count()
    )

    completed_count = (
        completable_owned_entries
        .filter(
            Q(status=LibraryEntry.Status.COMPLETED)
            | Q(
                playthroughs__status=(
                    Playthrough.Status.COMPLETED
                )
            )
        )
        .distinct()
        .count()
    )

    platinum_count = LibraryEntry.objects.filter(
        has_platinum=True
    ).count()

    plan_to_play_count = LibraryEntry.objects.filter(
        status=LibraryEntry.Status.PLAN_TO_PLAY
    ).count()

    multiplayer_count = LibraryEntry.objects.filter(
        status=LibraryEntry.Status.MULTIPLAYER
    ).count()

    completion_ratio = (
        round(
            (
                completed_count
                / completable_owned_count
            )
            * 100
        )
        if completable_owned_count
        else 0
    )

    context = {
        "owned_count": owned_count,
        "wishlist_count": wishlist_count,
        "completed_count": completed_count,
        "platinum_count": platinum_count,
        "plan_to_play_count": plan_to_play_count,
        "multiplayer_count": multiplayer_count,
        "completion_ratio": completion_ratio,
        "active_entries": entries.filter(
            status=LibraryEntry.Status.PLAYING
        ).order_by("-updated_at")[:6],
        "multiplayer_entries": entries.filter(
            status=LibraryEntry.Status.MULTIPLAYER
        ).order_by("-updated_at")[:6],
        "library_preview": entries.order_by(
            "-updated_at",
            "game__title",
        )[:8],
        "recent_playthroughs": (
            Playthrough.objects
            .select_related(
                "library_entry__game",
                "access",
            )
            .order_by("-updated_at")[:6]
        ),
        "completable_owned_count": completable_owned_count,
        "active_page": "dashboard",
    }

    return render(
        request,
        "games/dashboard.html",
        context,
    )