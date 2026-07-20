from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import get_object_or_404, render

from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough,
)


def detail(request, slug):
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
                to_attr="detail_accesses",
            ),
            Prefetch(
                "playthroughs",
                queryset=(
                    Playthrough.objects
                    .select_related("access")
                    .order_by("-number")
                ),
                to_attr="detail_playthroughs",
            ),
        )
        .annotate(
            has_completed_history=Exists(
                completed_playthroughs
            ),
        )
    )

    entry = get_object_or_404(
        entries,
        game__slug=slug,
    )

    active_playthrough = next(
        (
            playthrough
            for playthrough in entry.detail_playthroughs
            if playthrough.status == Playthrough.Status.PLAYING
        ),
        None,
    )

    owned_accesses = [
        access
        for access in entry.detail_accesses
        if access.access_type == GameAccess.AccessType.OWNED
    ]

    wishlist_accesses = [
        access
        for access in entry.detail_accesses
        if access.access_type == GameAccess.AccessType.WISHLIST
    ]

    context = {
        "active_page": "library",
        "entry": entry,
        "game": entry.game,
        "active_playthrough": active_playthrough,
        "owned_accesses": owned_accesses,
        "wishlist_accesses": wishlist_accesses,
    }

    return render(
        request,
        "games/detail.html",
        context,
    )