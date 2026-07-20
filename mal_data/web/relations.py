from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from mal_data.models import (
    AnimeEntry,
    AnimeMetadata,
    AnimeRelation,
)
from mal_data.services.anime_relations_sync import sync_anime_relations

def anime_relations_detail(request, mal_id):
    anime = AnimeEntry.objects.filter(mal_id=mal_id).first()

    anime_metadata = None

    if anime is None:
        anime_metadata = AnimeMetadata.objects.filter(
            mal_id=mal_id
        ).first()

    sync_result = None
    sync_error = None

    def relation_sort_key(relation):
        relation_type_priority = {
            "sequel": 0,
            "prequel": 1,
            "parent_story": 2,
            "side_story": 3,
            "spin_off": 4,
            "alternative_version": 5,
            "alternative_setting": 6,
            "summary": 7,
            "full_story": 8,
            "other": 9,
            "character": 10,
        }

        media_type_priority = {
            "movie": 0,
            "ova": 1,
            "special": 2,
            "tv_special": 3,
            "ona": 4,
            "tv": 5,
            "music": 8,
            "pv": 9,
            "cm": 10,
        }

        status_priority = {
            "watching": 0,
            "completed": 1,
            "plan_to_watch": 2,
            "on_hold": 3,
            "dropped": 4,
        }

        local_status = relation.target_local_list_status

        local_group = 0 if local_status else 1
        local_status_order = status_priority.get(local_status, 99)

        media_type = relation.target_display_media_type
        media_type_order = media_type_priority.get(
            str(media_type).lower() if media_type else "",
            99,
        )

        try:
            score = int(relation.target_display_score)
        except (TypeError, ValueError):
            score = 0

        return (
            0 if relation.relation_source_type == "anime" else 1,
            local_group,
            local_status_order,
            relation_type_priority.get(relation.relation_type, 99),
            media_type_order,
            -score,
            relation.target_display_title.lower(),
        )


    relations = list(
        AnimeRelation.objects.filter(source_mal_id=mal_id)
    )

    relations = sorted(relations, key=relation_sort_key)

    anime_relations = [
        relation
        for relation in relations
        if relation.relation_source_type == "anime"
    ]

    manga_relations = [
        relation
        for relation in relations
        if relation.relation_source_type == "manga"
    ]

    low_priority_relation_types = {
        "summary",
        "character",
        "other",
    }

    low_priority_media_types = {
        "music",
        "pv",
        "cm",
    }

    priority_relation_types = {
        "sequel",
        "prequel",
        "parent_story",
        "full_story",
        "side_story",
        "spin_off",
        "alternative_version",
        "alternative_setting",
    }

    local_priority_nodes = []
    local_completed_nodes = []
    external_priority_nodes = []
    external_low_priority_nodes = []
    unknown_nodes = []

    for relation in anime_relations:
        media_type = (relation.target_display_media_type or "").lower()
        relation_type = relation.relation_type or ""

        is_low_priority = (
            relation_type in low_priority_relation_types
            or media_type in low_priority_media_types
        )

        if relation.has_local_target:
            target_entry = relation.target_anime_entry
            local_status = target_entry.list_status if target_entry else relation.target_local_list_status

            if local_status == "completed":
                local_completed_nodes.append(relation)
            elif local_status != "dropped":
                local_priority_nodes.append(relation)
            else:
                external_low_priority_nodes.append(relation)

        elif relation.is_external_metadata_node:
            if is_low_priority:
                external_low_priority_nodes.append(relation)
            elif relation_type in priority_relation_types:
                external_priority_nodes.append(relation)
            else:
                external_low_priority_nodes.append(relation)

        else:
            unknown_nodes.append(relation)

    franchise_audit = {
        "local_priority_nodes": local_priority_nodes,
        "local_completed_nodes": local_completed_nodes,
        "external_priority_nodes": external_priority_nodes,
        "external_low_priority_nodes": external_low_priority_nodes,
        "unknown_nodes": unknown_nodes,
        "local_priority_count": len(local_priority_nodes),
        "local_completed_count": len(local_completed_nodes),
        "external_priority_count": len(external_priority_nodes),
        "external_low_priority_count": len(external_low_priority_nodes),
        "unknown_count": len(unknown_nodes),
    }

    if anime:
        source_title = anime.display_title
        source_picture_url = anime.main_picture_url
        source_status = anime.personal_status_label
        source_progress = f"{anime.num_episodes_watched} / {anime.num_episodes or 'TBD'}"
    elif anime_metadata:
        source_title = anime_metadata.display_title
        source_picture_url = anime_metadata.main_picture_url
        source_status = "Not local"
        source_progress = f"- / {anime_metadata.num_episodes or 'TBD'}"
    else:
        source_title = "Unknown Source Node"
        source_picture_url = ""
        source_status = "Unknown"
        source_progress = "-"
    
    context = {
        "anime": anime,
        "mal_id": mal_id,
        "anime_relations": anime_relations,
        "manga_relations": manga_relations,
        "total_relations": len(relations),
        "sync_result": sync_result,
        "sync_error": sync_error,
        "source_title": source_title,
        "source_picture_url": source_picture_url,
        "source_status": source_status,
        "source_progress": source_progress,
        "franchise_audit": franchise_audit,
    }

    return render(request, "mal_data/anime_relations_detail.html", context)

@login_required
@require_POST
def sync_anime_relations_view(request, mal_id):

    try:
        result = sync_anime_relations(mal_id)

        messages.success(
            request,
            (
                "Relaciones actualizadas desde MAL. "
                f"Anime relacionados: {result['related_anime_count']} · "
                f"Manga relacionados: {result['related_manga_count']}"
            ),
        )
    except Exception as error:
        messages.error(
            request,
            f"No se pudieron actualizar las relaciones: {error}",
        )

    return redirect("mal_insights:anime_relations_detail", mal_id=mal_id)