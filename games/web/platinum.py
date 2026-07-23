from django.shortcuts import render

from games.models import LibraryEntry


def platinum(request):
    entries = (
        LibraryEntry.objects
        .select_related(
            "game",
            "game__franchise",
        )
    )

    dated_platinums = list(
        entries
        .filter(
            has_platinum=True,
            platinum_earned_on__isnull=False,
        )
        .order_by(
            "-platinum_earned_on",
            "game__title",
        )
    )

    undated_platinums = list(
        entries
        .filter(
            has_platinum=True,
            platinum_earned_on__isnull=True,
        )
        .order_by(
            "game__title",
        )
    )

    platinum_targets = list(
        entries
        .filter(
            is_platinum_target=True,
        )
        .order_by(
            "game__title",
        )
    )

    platinum_count = (
        len(dated_platinums)
        + len(undated_platinums)
    )

    context = {
        "active_page": "platinum",
        "platinum_count": platinum_count,
        "dated_platinums": dated_platinums,
        "undated_platinums": undated_platinums,
        "platinum_targets": platinum_targets,
        "latest_platinum": (
            dated_platinums[0]
            if dated_platinums
            else None
        ),
    }

    return render(
        request,
        "games/platinum.html",
        context,
    )


