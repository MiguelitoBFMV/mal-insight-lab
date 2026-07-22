import re
import unicodedata

import requests

from django.conf import settings
from django.core.cache import cache


TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_API_BASE_URL = "https://api.igdb.com/v4"

TOKEN_CACHE_KEY = "igdb:app-access-token"

TOKEN_TIMEOUT_SECONDS = 10
API_TIMEOUT_SECONDS = 15


SEARCH_POOL_LIMIT = 100

SECONDARY_TITLE_MARKERS = (
    "bundle",
    "collection",
    "edition",
    "game of the year",
    "goty",
    "pack",
    "season pass",
    "soundtrack",
    "demo",
    "dlc",
)


def normalize_search_title(
    value,
):
    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )

    text = (
        text
        .casefold()
        .replace("’", "'")
        .replace("'", "")
    )

    text = re.sub(
        r"[^\w]+",
        " ",
        text,
        flags=re.UNICODE,
    )

    return " ".join(
        text.split()
    )


def is_secondary_search_result(
    normalized_title,
):
    return any(
        marker in normalized_title
        for marker in SECONDARY_TITLE_MARKERS
    )


def get_search_result_rank(
    game,
    normalized_query,
):
    normalized_title = normalize_search_title(
        game.get("name")
    )

    is_secondary = (
        is_secondary_search_result(
            normalized_title
        )
    )

    if normalized_title == normalized_query:
        match_group = 0

    elif normalized_title.startswith(
        normalized_query
    ):
        match_group = (
            3
            if is_secondary
            else 1
        )

    elif normalized_query in normalized_title:
        match_group = (
            4
            if is_secondary
            else 2
        )

    else:
        match_group = (
            6
            if is_secondary
            else 5
        )

    rating_count = (
        game.get("total_rating_count")
        or game.get("rating_count")
        or 0
    )

    try:
        rating_count = int(
            rating_count
        )
    except (TypeError, ValueError):
        rating_count = 0

    return (
        match_group,
        -rating_count,
        abs(
            len(normalized_title)
            - len(normalized_query)
        ),
        normalized_title,
    )

class IGDBClientError(Exception):
    """Base exception for IGDB integration errors."""


class IGDBConfigurationError(IGDBClientError):
    """Raised when IGDB credentials are missing."""


class IGDBAuthenticationError(IGDBClientError):
    """Raised when Twitch authentication fails."""


class IGDBRequestError(IGDBClientError):
    """Raised when an IGDB API request fails."""


class IGDBClient:
    def __init__(self):
        self.client_id = settings.IGDB_CLIENT_ID
        self.client_secret = settings.IGDB_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            raise IGDBConfigurationError(
                "IGDB credentials are not configured."
            )

    def _request_access_token(
        self,
    ):
        try:
            response = requests.post(
                TWITCH_TOKEN_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=TOKEN_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise IGDBAuthenticationError(
                "Could not connect to Twitch authentication."
            ) from error

        if not response.ok:
            raise IGDBAuthenticationError(
                (
                    "Twitch authentication failed "
                    f"with status {response.status_code}."
                )
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise IGDBAuthenticationError(
                "Twitch returned an invalid authentication response."
            ) from error

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")

        if not access_token or not expires_in:
            raise IGDBAuthenticationError(
                "Twitch did not return a usable access token."
            )

        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError) as error:
            raise IGDBAuthenticationError(
                "Twitch returned an invalid token expiration."
            ) from error

        cache_timeout = max(
            expires_in - 60,
            60,
        )

        cache.set(
            TOKEN_CACHE_KEY,
            access_token,
            timeout=cache_timeout,
        )

        return access_token

    def get_access_token(
        self,
        *,
        force_refresh=False,
    ):
        if force_refresh:
            cache.delete(TOKEN_CACHE_KEY)
        else:
            cached_token = cache.get(
                TOKEN_CACHE_KEY
            )

            if cached_token:
                return cached_token

        return self._request_access_token()

    def request(
        self,
        endpoint,
        query,
        *,
        retry_on_unauthorized=True,
    ):
        access_token = self.get_access_token()

        try:
            response = requests.post(
                (
                    f"{IGDB_API_BASE_URL}/"
                    f"{endpoint.lstrip('/')}"
                ),
                headers={
                    "Accept": "application/json",
                    "Client-ID": self.client_id,
                    "Authorization": (
                        f"Bearer {access_token}"
                    ),
                },
                data=query,
                timeout=API_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise IGDBRequestError(
                "Could not connect to IGDB."
            ) from error

        if (
            response.status_code == 401
            and retry_on_unauthorized
        ):
            self.get_access_token(
                force_refresh=True
            )

            return self.request(
                endpoint,
                query,
                retry_on_unauthorized=False,
            )

        if response.status_code == 429:
            raise IGDBRequestError(
                (
                    "IGDB rate limit reached. "
                    "Try again in a moment."
                )
            )

        if not response.ok:
            response_preview = response.text[:300]

            raise IGDBRequestError(
                (
                    "IGDB request failed with status "
                    f"{response.status_code}: "
                    f"{response_preview}"
                )
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise IGDBRequestError(
                "IGDB returned an invalid JSON response."
            ) from error

        if not isinstance(payload, list):
            raise IGDBRequestError(
                "IGDB returned an unexpected response."
            )

        return payload

    def get_game_time_to_beat(
        self,
        igdb_id,
    ):
        try:
            igdb_id = int(igdb_id)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise IGDBRequestError(
                "The IGDB game ID must be numeric."
            ) from error

        query = f"""
            fields
                game_id,
                hastily,
                normally,
                completely,
                count;
            where game_id = {igdb_id};
            limit 1;
        """

        results = self.request(
            "game_time_to_beats",
            query,
        )

        if not results:
            return None

        return results[0]

    def search_games(
        self,
        search_term,
        *,
        limit=10,
    ):
        search_term = search_term.strip()

        if not search_term:
            return []

        safe_limit = max(
            1,
            min(
                int(limit),
                30,
            ),
        )

        escaped_term = (
            search_term
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        fuzzy_term = (
            search_term
            .replace("’", "")
            .replace("'", "")
        )

        fuzzy_term = (
            fuzzy_term
            or search_term
        )

        escaped_fuzzy_term = (
            fuzzy_term
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        fields = """
            fields
                id,
                name,
                slug,
                summary,
                first_release_date,
                cover.image_id,
                artworks.image_id,
                genres.name,
                platforms.name,
                rating_count,
                total_rating_count;
        """

        literal_query = f"""
            {fields}
            where
                name ~ *"{escaped_term}"*
                & version_parent = null;
            limit {SEARCH_POOL_LIMIT};
        """

        fuzzy_query = f"""
            search "{escaped_fuzzy_term}";
            {fields}
            where version_parent = null;
            limit {SEARCH_POOL_LIMIT};
        """

        literal_results = self.request(
            "games",
            literal_query,
        )

        fuzzy_results = self.request(
            "games",
            fuzzy_query,
        )

        merged_results = {}

        for game in (
            literal_results
            + fuzzy_results
        ):
            game_id = game.get("id")

            if game_id is None:
                continue

            merged_results[game_id] = game

        normalized_query = (
            normalize_search_title(
                search_term
            )
        )

        ranked_results = sorted(
            merged_results.values(),
            key=lambda game: (
                get_search_result_rank(
                    game,
                    normalized_query,
                )
            ),
        )

        return ranked_results[
            :safe_limit
        ]

    def get_game(
        self,
        igdb_id,
    ):
        try:
            igdb_id = int(igdb_id)
        except (TypeError, ValueError) as error:
            raise IGDBRequestError(
                "The IGDB game ID must be numeric."
            ) from error

        query = f"""
            fields
                id,
                name,
                slug,
                summary,
                first_release_date,
                cover.image_id,
                artworks.image_id,
                genres.name,
                platforms.name,
                game_type.type,
                parent_game.id,
                parent_game.name,
                dlcs.id,
                dlcs.name,
                dlcs.slug,
                dlcs.summary,
                dlcs.first_release_date,
                dlcs.cover.image_id,
                expansions.id,
                expansions.name,
                expansions.slug,
                expansions.summary,
                expansions.first_release_date,
                expansions.cover.image_id,
                standalone_expansions.id,
                standalone_expansions.name,
                standalone_expansions.slug,
                standalone_expansions.summary,
                standalone_expansions.first_release_date,
                standalone_expansions.cover.image_id;
            where id = {igdb_id};
            limit 1;
        """

        results = self.request(
            "games",
            query,
        )

        if not results:
            return None

        return results[0]