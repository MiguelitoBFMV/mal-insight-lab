from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render)
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest

from games.forms import (
    LibraryEntryOwnerForm,
    PlaythroughOwnerForm,
)
from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough)
from games.services.playthrough_state import change_playthrough_state


def _detail_entries():
    completed_playthroughs = Playthrough.objects.filter(
        library_entry=OuterRef("pk"),
        status=Playthrough.Status.COMPLETED,
    )

    return (
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


def _get_detail_entry(slug):
    return get_object_or_404(
        _detail_entries(),
        game__slug=slug,
    )


def _build_detail_context(
    entry,
    owner_form=None,
    playthrough_form=None,
):
    current_playthrough = next(
        (
            playthrough
            for playthrough in entry.detail_playthroughs
            if (
                playthrough.status
                == Playthrough.Status.PLAYING
            )
        ),
        None,
    )

    if current_playthrough is None:
        current_playthrough = next(
            (
                playthrough
                for playthrough
                in entry.detail_playthroughs
                if (
                    playthrough.status
                    == Playthrough.Status.PAUSED
                )
            ),
            None,
        )

    owned_accesses = [
        access
        for access in entry.detail_accesses
        if (
            access.access_type
            == GameAccess.AccessType.OWNED
        )
    ]

    wishlist_accesses = [
        access
        for access in entry.detail_accesses
        if (
            access.access_type
            == GameAccess.AccessType.WISHLIST
        )
    ]

    if owner_form is None:
        owner_form = LibraryEntryOwnerForm(
            instance=entry,
        )

    for playthrough in entry.detail_playthroughs:
        if (
            playthrough_form is not None
            and playthrough.pk
            == playthrough_form.instance.pk
        ):
            playthrough.owner_form = playthrough_form
        else:
            playthrough.owner_form = PlaythroughOwnerForm(
                instance=playthrough,
                library_entry=entry,
                prefix=f"playthrough-{playthrough.pk}",
            )

    return {
        "active_page": "library",
        "entry": entry,
        "game": entry.game,
        "current_playthrough": current_playthrough,
        "owned_accesses": owned_accesses,
        "wishlist_accesses": wishlist_accesses,
        "owner_form": owner_form,
    }


def detail(request, slug):
    entry = _get_detail_entry(slug)

    return render(
        request,
        "games/detail.html",
        _build_detail_context(entry),
    )


@login_required
@require_POST
def update_entry(request, slug):
    entry = _get_detail_entry(slug)

    form = LibraryEntryOwnerForm(
        request.POST,
        instance=entry,
    )

    if form.is_valid():
        form.save()

        return redirect(
            entry.game.get_absolute_url()
        )

    return render(
        request,
        "games/detail.html",
        _build_detail_context(
            entry,
            owner_form=form,
        ),
    )


@login_required
@require_POST
def update_playthrough(
    request,
    slug,
    playthrough_id,
):
    entry = _get_detail_entry(slug)

    playthrough = get_object_or_404(
        Playthrough.objects.select_related(
            "library_entry",
            "access",
        ),
        pk=playthrough_id,
        library_entry=entry,
    )

    form = PlaythroughOwnerForm(
        request.POST,
        instance=playthrough,
        library_entry=entry,
        prefix=f"playthrough-{playthrough.pk}",
    )

    if form.is_valid():
        form.save()

        return redirect(
            entry.game.get_absolute_url()
        )

    return render(
        request,
        "games/detail.html",
        _build_detail_context(
            entry,
            playthrough_form=form,
        ),
    )


@login_required
@require_POST
def update_playthrough_state(
    request,
    slug,
    playthrough_id,
):
    entry = get_object_or_404(
        LibraryEntry.objects.select_related("game"),
        game__slug=slug,
    )

    playthrough = get_object_or_404(
        Playthrough.objects.select_related(
            "library_entry",
        ),
        pk=playthrough_id,
        library_entry=entry,
    )

    action = request.POST.get(
        "action",
        "",
    )

    try:
        change_playthrough_state(
            playthrough=playthrough,
            action=action,
        )
    except ValueError as error:
        return HttpResponseBadRequest(
            str(error)
        )

    return redirect(
        entry.game.get_absolute_url()
    )

