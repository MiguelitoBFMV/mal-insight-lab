from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import Http404
from django.shortcuts import redirect, render

from mal_data.models import AnimeEntry

def anime_status_list(request, status):
    valid_statuses = {
        "all": "All anime",
        "watching": "Watching",
        "completed": "Completed",
        "plan_to_watch": "Plan to watch",
        "on_hold": "On hold",
        "dropped": "Dropped",
    }

    if status not in valid_statuses:
        raise Http404("Estado de anime no válido")

    status_order = [
        "watching",
        "completed",
        "plan_to_watch",
        "on_hold",
        "dropped",
    ]

    status_filter_options = [
        (status_key, valid_statuses[status_key])
        for status_key in status_order
    ]

    selected_statuses_query = ""

    if status == "all":
        selected_statuses = request.GET.getlist("statuses")

        if not selected_statuses:
            selected_statuses = status_order.copy()

        selected_statuses = [
            selected_status
            for selected_status in selected_statuses
            if selected_status in status_order
        ]

        if len(selected_statuses) == 1:
            return redirect("mal_insights:anime_status_list", status=selected_statuses[0])

        if not selected_statuses:
            selected_statuses = status_order.copy()

        selected_statuses_query = "".join(
            f"&statuses={selected_status}"
            for selected_status in selected_statuses
        )

        anime_entries = AnimeEntry.objects.filter(
            list_status__in=selected_statuses
        )
    else:
        selected_statuses = [status]

        if status == "watching":
            anime_entries = AnimeEntry.objects.filter(
                Q(list_status="watching") | Q(is_rewatching=True)
            )
        else:
            anime_entries = AnimeEntry.objects.filter(list_status=status)

    airing_filter = request.GET.get("airing")

    valid_airing_statuses = {
        "finished_airing": "Finalizados",
        "currently_airing": "En emisión",
        "not_yet_aired": "Por emitir",
    }

    if airing_filter in valid_airing_statuses:
        anime_entries = anime_entries.filter(airing_status=airing_filter)
    else:
        airing_filter = None

    # Orden inicial según el tipo de lista
    sort = request.GET.get("sort")

    allowed_sorts = {
        "title": "title",
        "-title": "-title",
        "score": "score",
        "-score": "-score",
        "num_episodes": "num_episodes",
        "-num_episodes": "-num_episodes",
        "num_episodes_watched": "num_episodes_watched",
        "-num_episodes_watched": "-num_episodes_watched",
        "airing_status": "airing_status",
        "-airing_status": "-airing_status",
        "updated_at_mal": "updated_at_mal",
        "-updated_at_mal": "-updated_at_mal",
        "media_type": "media_type",
        "-media_type": "-media_type",
    }

    if sort in allowed_sorts:
        anime_entries = anime_entries.order_by(allowed_sorts[sort])
    else:
        if status == "all":
            sort = "status_priority"

            status_priority = Case(
                When(list_status="watching", then=Value(0)),
                When(list_status="completed", then=Value(1)),
                When(list_status="plan_to_watch", then=Value(2)),
                When(list_status="on_hold", then=Value(3)),
                When(list_status="dropped", then=Value(4)),
                default=Value(99),
                output_field=IntegerField(),
            )

            anime_entries = anime_entries.annotate(
                status_priority=status_priority
            ).order_by(
                "status_priority",
                "-updated_at_mal",
                "title",
            )

        elif status == "plan_to_watch":
            sort = "title"
            anime_entries = anime_entries.order_by("title")
        elif status in {"completed", "dropped"}:
            sort = "-updated_at_mal"
            anime_entries = anime_entries.order_by("-updated_at_mal")
        elif status == "on_hold":
            sort = "title"
            anime_entries = anime_entries.order_by("title")
        else:
            sort = "-updated_at_mal"
            anime_entries = anime_entries.order_by("-updated_at_mal")

    paginator = Paginator(anime_entries, 50)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "status": status,
        "status_label": valid_statuses[status],
        "page_obj": page_obj,
        "anime_entries": page_obj.object_list,
        "total_entries": paginator.count,
        "airing_filter": airing_filter,
        "valid_airing_statuses": valid_airing_statuses,
        "sort": sort,
        "status_order": status_order,
        "selected_statuses": selected_statuses,
        "status_filter_options": status_filter_options,
        "selected_statuses_query": selected_statuses_query,
    }

    return render(request, "mal_data/anime_status_list.html", context)

