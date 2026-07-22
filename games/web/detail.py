from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Prefetch
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render)
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest

from games.forms import (
    GameAccessOwnerForm,
    GameContentOwnerForm,
    IGDBGameContentTrackForm,
    LibraryEntryOwnerForm,
    NewPlaythroughForm,
    PlaythroughOwnerForm,
)
from games.models import (
    Game,
    GameAccess,
    GameContent,
    LibraryEntry,
    Playthrough,
)
from games.services.playthrough_state import (
    change_playthrough_state,
    start_new_playthrough,
)
from games.services.igdb_normalizer import (
    build_igdb_image_url,
    unix_timestamp_to_date,
)

IGDB_CONTENT_RELATIONS = (
    (
        "dlcs",
        GameContent.ContentType.DLC,
    ),
    (
        "expansions",
        GameContent.ContentType.EXPANSION,
    ),
    (
        "standalone_expansions",
        GameContent.ContentType.STANDALONE_EXPANSION,
    ),
)


def _normalize_igdb_content_item(
    payload,
    content_type,
):
    if not isinstance(payload, dict):
        return None

    try:
        igdb_id = int(
            payload.get("id")
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    title = str(
        payload.get("name") or ""
    ).strip()

    if not title:
        return None

    cover = payload.get("cover")

    if not isinstance(cover, dict):
        cover = {}

    return {
        "igdb_id": igdb_id,
        "title": title,
        "content_type": content_type,
        "content_type_label": dict(
            GameContent.ContentType.choices
        ).get(
            content_type,
            "Other",
        ),
        "summary": str(
            payload.get("summary") or ""
        ).strip(),
        "cover_url": build_igdb_image_url(
            cover.get("image_id"),
            size="cover_big_2x",
        ),
        "first_release_date": (
            unix_timestamp_to_date(
                payload.get(
                    "first_release_date"
                )
            )
        ),
        "igdb_payload": payload,
    }


def _iter_igdb_content_items(
    game,
):
    payload = game.igdb_payload

    if not isinstance(payload, dict):
        return

    seen_ids = set()

    for (
        relation_name,
        content_type,
    ) in IGDB_CONTENT_RELATIONS:
        related_items = (
            payload.get(relation_name)
            or []
        )

        if not isinstance(
            related_items,
            list,
        ):
            continue

        for item in related_items:
            normalized_item = (
                _normalize_igdb_content_item(
                    item,
                    content_type,
                )
            )

            if normalized_item is None:
                continue

            igdb_id = normalized_item[
                "igdb_id"
            ]

            if igdb_id in seen_ids:
                continue

            seen_ids.add(igdb_id)

            yield normalized_item


def _find_igdb_content_item(
    game,
    igdb_content_id,
):
    try:
        igdb_content_id = int(
            igdb_content_id
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    return next(
        (
            item
            for item
            in _iter_igdb_content_items(
                game
            )
            if (
                item["igdb_id"]
                == igdb_content_id
            )
        ),
        None,
    )


def _build_detected_content(
    entry,
):
    tracked_igdb_ids = set(
        GameContent.objects.filter(
            library_entry=entry,
            igdb_id__isnull=False,
        ).values_list(
            "igdb_id",
            flat=True,
        )
    )

    detected_content = [
        item
        for item
        in _iter_igdb_content_items(
            entry.game
        )
        if (
            item["igdb_id"]
            not in tracked_igdb_ids
        )
    ]

    detected_ids = [
        item["igdb_id"]
        for item in detected_content
    ]

    local_games = {
        game.igdb_id: game
        for game in Game.objects.filter(
            igdb_id__in=detected_ids
        )
    }

    for item in detected_content:
        item["local_game"] = (
            local_games.get(
                item["igdb_id"]
            )
        )

    content_order = {
        GameContent.ContentType.DLC: 0,
        GameContent.ContentType.EXPANSION: 1,
        (
            GameContent.ContentType
            .STANDALONE_EXPANSION
        ): 2,
        GameContent.ContentType.OTHER: 3,
    }

    return sorted(
        detected_content,
        key=lambda item: (
            content_order.get(
                item["content_type"],
                99,
            ),
            (
                item["first_release_date"]
                is None
            ),
            item["first_release_date"],
            item["title"].casefold(),
        ),
    )


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
                        Prefetch(
                "additional_contents",
                queryset=(
                    GameContent.objects
                    .order_by(
                        "content_type",
                        "first_release_date",
                        "title",
                    )
                ),
                to_attr=(
                    "detail_additional_contents"
                ),
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
    new_playthrough_form=None,
    new_access_form=None,
    access_form=None,
    new_content_form=None,
    content_form=None,
    detected_content_form=None,
    detected_content_id=None,
    access_action_error=None,
    access_action_id=None,
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

    if new_playthrough_form is None:
        new_playthrough_form = NewPlaythroughForm(
            library_entry=entry,
            prefix="new-playthrough",
        )

    if new_access_form is None:
        new_access_form = GameAccessOwnerForm(
            library_entry=entry,
            prefix="new-access",
        )

    for access in entry.detail_accesses:
        if (
            access_form is not None
            and access.pk == access_form.instance.pk
        ):
            access.owner_form = access_form
        else:
            access.owner_form = GameAccessOwnerForm(
                instance=access,
                library_entry=entry,
                prefix=f"access-{access.pk}",
            )

    if new_content_form is None:
        new_content_form = (
            GameContentOwnerForm(
                library_entry=entry,
                prefix="new-content",
            )
        )

    for content in (
        entry.detail_additional_contents
    ):
        if (
            content_form is not None
            and content.pk
            == content_form.instance.pk
        ):
            content.owner_form = content_form
        else:
            content.owner_form = (
                GameContentOwnerForm(
                    instance=content,
                    library_entry=entry,
                    prefix=(
                        f"content-{content.pk}"
                    ),
                )
            )

    detected_contents = (
        _build_detected_content(
            entry
        )
    )

    for detected_content in detected_contents:
        igdb_id = detected_content[
            "igdb_id"
        ]

        if (
            detected_content_form
            is not None
            and detected_content_id
            == igdb_id
        ):
            detected_content[
                "track_form"
            ] = detected_content_form
        else:
            detected_content[
                "track_form"
            ] = IGDBGameContentTrackForm(
                prefix=(
                    f"detected-content-"
                    f"{igdb_id}"
                ),
                initial={
                    "status": (
                        GameContent.Status
                        .PLAN_TO_PLAY
                    ),
                },
            )

    return {
        "active_page": "library",
        "entry": entry,
        "game": entry.game,
        "current_playthrough": current_playthrough,
        "owned_accesses": owned_accesses,
        "wishlist_accesses": wishlist_accesses,
        "owner_form": owner_form,
        "new_playthrough_form": new_playthrough_form,
        "new_access_form": new_access_form,
        "new_content_form": new_content_form,
        "detected_contents": detected_contents,
        "access_action_error": access_action_error,
        "access_action_id": access_action_id,
        "tracked_content_count": len(
            entry.detail_additional_contents
        ),
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

@login_required
@require_POST
def create_playthrough(
    request,
    slug,
):
    entry = _get_detail_entry(slug)

    form = NewPlaythroughForm(
        request.POST,
        library_entry=entry,
        prefix="new-playthrough",
    )

    if form.is_valid():
        try:
            start_new_playthrough(
                library_entry=entry,
                access=form.cleaned_data["access"],
                text_language=(
                    form.cleaned_data["text_language"]
                ),
                progress_note=(
                    form.cleaned_data["progress_note"]
                ),
                started_on=(
                    form.cleaned_data["started_on"]
                ),
                notes=form.cleaned_data["notes"],
            )
        except ValueError as error:
            form.add_error(
                None,
                str(error),
            )
        else:
            return redirect(
                entry.game.get_absolute_url()
            )

    return render(
        request,
        "games/detail.html",
        _build_detail_context(
            entry,
            new_playthrough_form=form,
        ),
    )


@login_required
@require_POST
def create_access(
    request,
    slug,
):
    entry = _get_detail_entry(slug)

    form = GameAccessOwnerForm(
        request.POST,
        library_entry=entry,
        prefix="new-access",
    )

    if form.is_valid():
        access = form.save(commit=False)
        access.library_entry = entry
        access.save()

        return redirect(
            entry.game.get_absolute_url()
        )

    return render(
        request,
        "games/detail.html",
        _build_detail_context(
            entry,
            new_access_form=form,
        ),
    )


@login_required
@require_POST
def update_access(
    request,
    slug,
    access_id,
):
    entry = _get_detail_entry(slug)

    access = get_object_or_404(
        GameAccess,
        pk=access_id,
        library_entry=entry,
    )

    form = GameAccessOwnerForm(
        request.POST,
        instance=access,
        library_entry=entry,
        prefix=f"access-{access.pk}",
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
            access_form=form,
        ),
    )


@login_required
@require_POST
def delete_access(
    request,
    slug,
    access_id,
):
    entry = _get_detail_entry(slug)

    access = get_object_or_404(
        GameAccess,
        pk=access_id,
        library_entry=entry,
    )

    access_is_in_use = Playthrough.objects.filter(
        access=access,
    ).exists()

    if access_is_in_use:
        return render(
            request,
            "games/detail.html",
            _build_detail_context(
                entry,
                access_action_error=(
                    "This access is used by one or more "
                    "playthroughs and cannot be deleted."
                ),
                access_action_id=access.pk,
            ),
            status=409,
        )


    removes_last_owned_access = (
        access.access_type
        == GameAccess.AccessType.OWNED
        and entry.has_platinum
        and not GameAccess.objects.filter(
            library_entry=entry,
            access_type=(
                GameAccess.AccessType.OWNED
            ),
        )
        .exclude(
            pk=access.pk
        )
        .exists()
    )

    if removes_last_owned_access:
        return render(
            request,
            "games/detail.html",
            _build_detail_context(
                entry,
                access_action_error=(
                    "This access is the final Owned "
                    "platform for a platinum-marked game. "
                    "Remove the platinum mark or add "
                    "another Owned access first."
                ),
                access_action_id=access.pk,
            ),
            status=409,
        )

    access.delete()

    return redirect(
        entry.game.get_absolute_url()
    )


@login_required
@require_POST
def create_manual_content(
    request,
    slug,
):
    entry = _get_detail_entry(slug)

    form = GameContentOwnerForm(
        request.POST,
        library_entry=entry,
        prefix="new-content",
    )

    if form.is_valid():
        content = form.save(
            commit=False
        )

        content.library_entry = entry
        content.save()

        return redirect(
            entry.game.get_absolute_url()
        )

    return render(
        request,
        "games/detail.html",
        _build_detail_context(
            entry,
            new_content_form=form,
        ),
    )


@login_required
@require_POST
def track_igdb_content(
    request,
    slug,
    igdb_content_id,
):
    entry = _get_detail_entry(slug)

    detected_content = (
        _find_igdb_content_item(
            entry.game,
            igdb_content_id,
        )
    )

    if detected_content is None:
        return HttpResponseBadRequest(
            (
                "This content is not related "
                "to the selected local game."
            )
        )

    if Game.objects.filter(
        igdb_id=igdb_content_id
    ).exists():
        return HttpResponseBadRequest(
            (
                "This IGDB content is already "
                "tracked as a separate game."
            )
        )

    if GameContent.objects.filter(
        igdb_id=igdb_content_id
    ).exists():
        return HttpResponseBadRequest(
            (
                "This IGDB content is already "
                "tracked under another game."
            )
        )

    form = IGDBGameContentTrackForm(
        request.POST,
        prefix=(
            f"detected-content-"
            f"{igdb_content_id}"
        ),
    )

    if form.is_valid():
        GameContent.objects.create(
            library_entry=entry,
            igdb_id=(
                detected_content[
                    "igdb_id"
                ]
            ),
            title=(
                detected_content[
                    "title"
                ]
            ),
            content_type=(
                detected_content[
                    "content_type"
                ]
            ),
            status=(
                form.cleaned_data[
                    "status"
                ]
            ),
            summary=(
                detected_content[
                    "summary"
                ]
            ),
            cover_url=(
                detected_content[
                    "cover_url"
                ]
            ),
            first_release_date=(
                detected_content[
                    "first_release_date"
                ]
            ),
            completed_on=(
                form.cleaned_data[
                    "completed_on"
                ]
            ),
            notes=(
                form.cleaned_data[
                    "notes"
                ]
            ),
            igdb_payload=(
                detected_content[
                    "igdb_payload"
                ]
            ),
        )

        return redirect(
            entry.game.get_absolute_url()
        )

    return render(
        request,
        "games/detail.html",
        _build_detail_context(
            entry,
            detected_content_form=form,
            detected_content_id=(
                igdb_content_id
            ),
        ),
    )


@login_required
@require_POST
def update_content(
    request,
    slug,
    content_id,
):
    entry = _get_detail_entry(slug)

    content = get_object_or_404(
        GameContent,
        pk=content_id,
        library_entry=entry,
    )

    form = GameContentOwnerForm(
        request.POST,
        instance=content,
        library_entry=entry,
        prefix=f"content-{content.pk}",
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
            content_form=form,
        ),
    )


@login_required
@require_POST
def delete_content(
    request,
    slug,
    content_id,
):
    entry = _get_detail_entry(slug)

    content = get_object_or_404(
        GameContent,
        pk=content_id,
        library_entry=entry,
    )

    content.delete()

    return redirect(
        entry.game.get_absolute_url()
    )

