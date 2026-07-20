from datetime import timedelta

from django.core.paginator import Paginator
from django.http import Http404
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.db.models import Case, IntegerField, Q, Value, When
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from mal_data.models import (
    AnimeAiringData,
    AnimeEntry,
    AnimeMetadata,
    AnimeRelation,
    AnimeSyncEvent,
    ManualTrackedAnime,
    SeasonalAnime
)
from mal_data.services.anime_relations_sync import sync_anime_relations
from mal_data.services.anime_list_sync import sync_all_anime_statuses, upsert_anime_entry
from mal_data.services.anilist_airing_sync import sync_airing_data_for_dashboard
from mal_data.services.anilist_client import AniListClient
from mal_data.services.manual_tracked_sync import sync_manual_tracked_anime_entries, sync_manual_tracked_anime_entry
from mal_data.services.mal_client import MyAnimeListClient
from mal_data.services.seasonal_sync import sync_seasonal_anime, sync_tba_upcoming_anime

def dashboard(request):
    now = timezone.now()
    three_months_ago = now - timedelta(days=90)

    anime_entries = AnimeEntry.objects.all()

    total_anime = anime_entries.count()

    watching_entries = anime_entries.filter(list_status="watching")
    on_hold_entries = anime_entries.filter(list_status="on_hold")
    plan_to_watch_entries = anime_entries.filter(list_status="plan_to_watch")
    completed_entries = anime_entries.filter(list_status="completed")
    dropped_entries = anime_entries.filter(list_status="dropped")
    rewatching_entries = anime_entries.filter(is_rewatching=True)

    broadcast_watchlist_entries = (
        plan_to_watch_entries.filter(airing_status="currently_airing").order_by("-updated_at_mal", "title")[:10]
    )

    episode_signal_data = (
        AnimeAiringData.objects
        .select_related("anime")
        .filter(
            Q(anime__list_status="watching")
            | Q(anime__is_rewatching=True)
        )
    )

    episode_signal_entries = [
        airing_data
        for airing_data in episode_signal_data
        if airing_data.pending_episodes_for_user > 0
    ]


    def episode_signal_priority(airing_data):
        anime = airing_data.anime
        is_finished = anime.airing_status == "finished_airing"
        is_rewatching = anime.is_rewatching
        is_longrun = (
            airing_data.episodes_aired_estimated >= 60
            or (anime.num_episodes and anime.num_episodes >= 60)
        )

        if is_rewatching:
            group = 3
        elif is_finished:
            group = 2
        elif is_longrun:
            group = 1
        else:
            group = 0

        next_airing_sort = (
            airing_data.next_airing_at.timestamp()
            if airing_data.next_airing_at
            else 0
        )

        return (
            group,
            -next_airing_sort,
            -airing_data.pending_episodes_for_user,
            anime.title,
        )


    episode_signal_entries = sorted(
        episode_signal_entries,
        key=episode_signal_priority,
    )[:15]

    fallback_active_entries = watching_entries.order_by("-updated_at_mal")[:4]

    watching_source_entries = list(watching_entries)

    rewatching_source_entries = list(
        rewatching_entries.exclude(
            mal_id__in=watching_entries.values_list("mal_id", flat=True)
        )
    )

    completed_source_entries = list(
        completed_entries.exclude(
            Q(is_rewatching=True)
            | Q(mal_id__in=watching_entries.values_list("mal_id", flat=True))
        )
    )

    priority_source_entries = (
        watching_source_entries
        + rewatching_source_entries
        + completed_source_entries
    )

    source_priority_by_mal_id = {
        anime.mal_id: index
        for index, anime in enumerate(priority_source_entries)
    }

    source_kind_by_mal_id = {}

    for anime in watching_source_entries:
        source_kind_by_mal_id[anime.mal_id] = "watching"

    for anime in rewatching_source_entries:
        source_kind_by_mal_id[anime.mal_id] = "rewatching"

    for anime in completed_source_entries:
        source_kind_by_mal_id[anime.mal_id] = "completed"

    source_mal_ids = [anime.mal_id for anime in priority_source_entries]

    sequel_relations = (
        AnimeRelation.objects
        .filter(
            source_mal_id__in=source_mal_ids,
            relation_source_type="anime",
            relation_type="sequel",
        )
    )

    sequel_recommendations = []
    seen_target_ids = set()

    broadcast_watchlist_ids = set(
        broadcast_watchlist_entries.values_list("mal_id", flat=True)
    )

    def compact_relation_title(title):
        if not title:
            return "Unknown title"

        compact_title = title.split(" (")[0]
        compact_title = compact_title.split("（")[0]

        return compact_title.strip()

    for relation in sequel_relations:
        if relation.target_mal_id in seen_target_ids:
            continue

        source_anime = AnimeEntry.objects.filter(
            mal_id=relation.source_mal_id
        ).first()

        source_kind = source_kind_by_mal_id.get(
            relation.source_mal_id,
            "completed",
        )

        target_anime = AnimeEntry.objects.filter(
            mal_id=relation.target_mal_id
        ).first()

        if target_anime and target_anime.mal_id in broadcast_watchlist_ids:
            continue

        if target_anime and target_anime.list_status == "watching":
            continue

        target_is_completed = (
            target_anime
            and target_anime.list_status == "completed"
        )

        is_rewatch_next_candidate = (
            source_kind == "rewatching"
            and target_is_completed
        )

        if target_is_completed and not is_rewatch_next_candidate:
            continue

        if is_rewatch_next_candidate:
            target_action_label = "Rewatch next"
            target_action_priority = 2
        elif target_anime and target_anime.list_status == "plan_to_watch":
            target_action_label = "Plan to Watch"
            target_action_priority = 0
        elif target_anime and target_anime.list_status == "on_hold":
            target_action_label = "On Hold"
            target_action_priority = 1
        elif target_anime and target_anime.list_status == "dropped":
            target_action_label = "Dropped"
            target_action_priority = 3
        else:
            target_action_label = "Not in local list"
            target_action_priority = 0

        recommendation = {
            "source_title": (
                source_anime.display_title
                if source_anime
                else relation.source_title
            ),
            "source_kind": source_kind,
            "target_title": (
                target_anime.display_title
                if target_anime
                else relation.target_title
            ),
            "target_mal_id": relation.target_mal_id,
            "target_status": (
                target_anime.personal_status_label
                if target_anime
                else "Not in local list"
            ),
            "target_airing_status": (
                target_anime.airing_status
                if target_anime
                else relation.target_status or "unknown"
            ),
            "target_action_label": target_action_label,
            "target_action_priority": target_action_priority,
            "source_priority": source_priority_by_mal_id.get(
                relation.source_mal_id,
                999,
            ),
            "target_compact_title": compact_relation_title(
                target_anime.display_title
                if target_anime
                else relation.target_title
            ),
            "source_compact_title": compact_relation_title(
                source_anime.display_title
                if source_anime
                else relation.source_title
            ),
        }

        sequel_recommendations.append(recommendation)
        seen_target_ids.add(relation.target_mal_id)

    sequel_recommendations = sorted(
        sequel_recommendations,
        key=lambda recommendation: (
            recommendation["source_priority"],
            recommendation["target_action_priority"],
            recommendation["target_title"].lower(),
        ),
    )[:10]

    currently_airing_count = anime_entries.filter(
        airing_status="currently_airing"
    ).count()

    finished_airing_count = anime_entries.filter(
        airing_status="finished_airing"
    ).count()

    old_watching_entries = watching_entries.filter(
        updated_at_mal__lt=three_months_ago
    ).order_by("updated_at_mal")

    recent_watching_entries = watching_entries.filter(
        updated_at_mal__gte=three_months_ago
    ).order_by("-updated_at_mal")

    almost_finished_entries = watching_entries.filter(
        num_episodes__gt=0,
        num_episodes_watched__gt=0,
    )

    almost_finished_entries = [
        anime
        for anime in almost_finished_entries
        if anime.num_episodes > 0
        and anime.num_episodes_watched / anime.num_episodes >= 0.7
    ]

    backlog_total = completed_entries.count() + plan_to_watch_entries.count()

    if backlog_total > 0:
        backlog_clear_ratio = round(completed_entries.count() / backlog_total * 100)
    else:
        backlog_clear_ratio = 0

    spotlight_anime = (
        watching_entries
        .exclude(title_japanese__isnull=True)
        .exclude(title_japanese="")
        .order_by("-score", "-updated_at_mal")
        .first()
    )

    latest_sync_events = (AnimeSyncEvent.objects.select_related("anime").order_by("-created_at")[:15])

    last_synced_entry = anime_entries.order_by("-last_synced_at").first()

    context = {
        "total_anime": total_anime,
        "watching_count": watching_entries.count(),
        "rewatching_count": rewatching_entries.count(),
        "currently_airing_count": currently_airing_count,
        "finished_airing_count": finished_airing_count,
        "old_watching_entries": old_watching_entries,
        "recent_watching_entries": recent_watching_entries,
        "almost_finished_entries": almost_finished_entries,
        "on_hold_count": on_hold_entries.count(),
        "plan_to_watch_count": plan_to_watch_entries.count(),
        "on_hold_entries": on_hold_entries.order_by("-score", "-updated_at_mal")[:10],
        "plan_to_watch_entries": plan_to_watch_entries.order_by("-updated_at_mal")[:10],
        "completed_count": completed_entries.count(),
        "dropped_count": dropped_entries.count(),
        "backlog_clear_ratio": backlog_clear_ratio,
        "backlog_total": backlog_total,
        "spotlight_anime": spotlight_anime,
        "latest_sync_events": latest_sync_events,
        "last_synced_entry": last_synced_entry,
        "sequel_recommendations": sequel_recommendations,
        "broadcast_watchlist_entries": broadcast_watchlist_entries,
        "episode_signal_entries": episode_signal_entries,
        "fallback_active_entries": fallback_active_entries,
    }

    return render(request, "mal_data/dashboard.html", context)

