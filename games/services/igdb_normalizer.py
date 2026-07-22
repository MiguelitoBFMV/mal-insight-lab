from copy import deepcopy
from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal, ROUND_HALF_UP

from django.utils.text import slugify


IGDB_IMAGE_BASE_URL = (
    "https://images.igdb.com/"
    "igdb/image/upload"
)

MIN_TIME_TO_BEAT_SUBMISSIONS = 3

class IGDBNormalizationError(ValueError):
    """Raised when an IGDB payload cannot be normalized."""


def build_igdb_image_url(
    image_id,
    *,
    size,
):
    if not image_id:
        return ""

    image_id = str(image_id).strip()

    if not image_id:
        return ""

    return (
        f"{IGDB_IMAGE_BASE_URL}/"
        f"t_{size}/"
        f"{image_id}.jpg"
    )


def unix_timestamp_to_date(
    timestamp,
):
    if timestamp in (None, ""):
        return None

    try:
        timestamp = int(timestamp)
    except (TypeError, ValueError):
        return None

    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=datetime_timezone.utc,
        ).date()
    except (
        OverflowError,
        OSError,
        ValueError,
    ):
        return None


def seconds_to_hours(
    seconds,
):
    if seconds in (None, ""):
        return None

    try:
        seconds = Decimal(str(seconds))
    except (
        TypeError,
        ValueError,
    ):
        return None

    if seconds <= 0:
        return None

    return (
        seconds / Decimal("3600")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def extract_names(
    items,
):
    if not isinstance(items, list):
        return []

    names = []

    for item in items:
        if not isinstance(item, dict):
            continue

        name = item.get("name")

        if not isinstance(name, str):
            continue

        name = name.strip()

        if (
            name
            and name not in names
        ):
            names.append(name)

    return names


def extract_first_artwork_id(
    artworks,
):
    if not isinstance(artworks, list):
        return None

    for artwork in artworks:
        if not isinstance(artwork, dict):
            continue

        image_id = artwork.get("image_id")

        if image_id:
            return image_id

    return None


def get_time_to_beat_record(
    payload,
):
    if isinstance(payload, dict):
        return payload

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item

    return None


def extract_main_story_hours(
    time_to_beat_payload,
):
    record = get_time_to_beat_record(
        time_to_beat_payload
    )

    if not record:
        return None

    try:
        submission_count = int(
            record.get("count") or 0
        )
    except (TypeError, ValueError):
        return None

    if (
        submission_count
        < MIN_TIME_TO_BEAT_SUBMISSIONS
    ):
        return None

    return seconds_to_hours(
        record.get("hastily")
    )


def normalize_game_payload(
    payload,
    *,
    time_to_beat_payload=None,
):
    if not isinstance(payload, dict):
        raise IGDBNormalizationError(
            "IGDB game payload must be a dictionary."
        )

    try:
        igdb_id = int(payload.get("id"))
    except (
        TypeError,
        ValueError,
    ) as error:
        raise IGDBNormalizationError(
            "IGDB game payload has no valid ID."
        ) from error

    title = str(
        payload.get("name") or ""
    ).strip()

    if not title:
        raise IGDBNormalizationError(
            "IGDB game payload has no title."
        )

    igdb_slug = str(
        payload.get("slug") or ""
    ).strip()

    normalized_slug = (
        igdb_slug
        or slugify(title)
        or f"igdb-{igdb_id}"
    )

    cover = payload.get("cover")

    if not isinstance(cover, dict):
        cover = {}

    cover_url = build_igdb_image_url(
        cover.get("image_id"),
        size="cover_big_2x",
    )

    artwork_image_id = (
        extract_first_artwork_id(
            payload.get("artworks")
        )
    )

    artwork_url = build_igdb_image_url(
        artwork_image_id,
        size="1080p",
    )

    raw_payload = deepcopy(payload)

    time_to_beat_record = (
        get_time_to_beat_record(
            time_to_beat_payload
        )
    )

    if time_to_beat_record:
        raw_payload["game_time_to_beat"] = (
            deepcopy(time_to_beat_record)
        )

    return {
        "igdb_id": igdb_id,
        "title": title,
        "slug": normalized_slug,
        "summary": str(
            payload.get("summary") or ""
        ).strip(),
        "cover_url": cover_url,
        "artwork_url": artwork_url,
        "first_release_date": (
            unix_timestamp_to_date(
                payload.get(
                    "first_release_date"
                )
            )
        ),
        "igdb_main_story_hours": (
            extract_main_story_hours(
                time_to_beat_payload
            )
        ),
        "genres": extract_names(
            payload.get("genres")
        ),
        "platforms": extract_names(
            payload.get("platforms")
        ),
        "igdb_payload": raw_payload,
    }