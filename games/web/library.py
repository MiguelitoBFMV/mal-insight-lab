from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import render

from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough,
)


def library(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    access_type = request.GET.get("access", "").strip()
    platform = request.GET.get("platform", "").strip()

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
                to_attr="library_accesses",
            ),
            Prefetch(
                "playthroughs",
                queryset=(
                    Playthrough.objects
                    .select_related("access")
                    .order_by("-number")
                ),
                to_attr="library_playthroughs",
            ),
        )
        .annotate(
            has_completed_history=Exists(
                completed_playthroughs
            ),
        )
    )

    if query:
        entries = entries.filter(
            Q(game__title__icontains=query)
            | Q(game__title_japanese__icontains=query)
            | Q(game__franchise__name__icontains=query)
        )

    valid_statuses = {
        value
        for value, _label in LibraryEntry.Status.choices
    }

    if status == "completed_once":
        entries = entries.filter(
            Q(status=LibraryEntry.Status.COMPLETED)
            | Q(
                playthroughs__status=(
                    Playthrough.Status.COMPLETED
                )
            )
        )
    elif status in valid_statuses:
        entries = entries.filter(status=status)

    valid_access_types = {
        value
        for value, _label in GameAccess.AccessType.choices
    }

    if access_type in valid_access_types:
        entries = entries.filter(
            accesses__access_type=access_type
        )

    valid_platforms = {
        value
        for value, _label in GameAccess.Platform.choices
    }

    if platform in valid_platforms:
        entries = entries.filter(
            accesses__platform_name=platform
        )

    entries = entries.distinct().order_by(
        "game__title"
    )

    context = {
        "active_page": "library",
        "active_access": access_type,
        "active_status": status,
        "entries": entries,
        "result_count": entries.count(),
        "query": query,
        "selected_status": status,
        "selected_access": access_type,
        "selected_platform": platform,
        "status_choices": LibraryEntry.Status.choices,
        "access_choices": GameAccess.AccessType.choices,
        "platform_choices": GameAccess.Platform.choices,
    }

    return render(
        request,
        "games/library.html",
        context,
    )