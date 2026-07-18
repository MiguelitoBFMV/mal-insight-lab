import requests


class AniListClient:
    API_URL = "https://graphql.anilist.co"

    def fetch_anime_by_mal_id(self, mal_id):
        query = """
        query ($malId: Int!) {
            Media(idMal: $malId, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                status
                episodes
                nextAiringEpisode {
                    episode
                    airingAt
                    timeUntilAiring
                }
                airingSchedule(notYetAired: true, perPage: 5) {
                    nodes {
                        episode
                        airingAt
                        timeUntilAiring
                    }
                }
                externalLinks {
                    site
                    url
                    type
                    language
                }
                streamingEpisodes {
                    title
                    thumbnail
                    url
                    site
                }
            }
        }
        """

        response = requests.post(
            self.API_URL,
            json={
                "query": query,
                "variables": {
                    "malId": mal_id,
                },
            },
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"AniList API error {response.status_code}: {response.text}"
            )

        payload = response.json()

        if "errors" in payload:
            raise Exception(payload["errors"])

        return payload.get("data", {}).get("Media")
    
    def search_anime(self, search):
        query = """
        query ($search: String!) {
            Media(search: $search, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                status
                episodes
                nextAiringEpisode {
                    episode
                    airingAt
                    timeUntilAiring
                }
            }
        }
        """

        response = requests.post(
            self.API_URL,
            json={
                "query": query,
                "variables": {
                    "search": search,
                },
            },
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"AniList API error {response.status_code}: {response.text}"
            )

        payload = response.json()

        if "errors" in payload:
            raise Exception(payload["errors"])

        return payload.get("data", {}).get("Media")
    
    def search_anime_candidates(self, search, per_page=10):
        query = """
        query ($search: String!, $perPage: Int!) {
            Page(page: 1, perPage: $perPage) {
                media(search: $search, type: ANIME) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    status
                    episodes
                    coverImage {
                        large
                        medium
                    }
                    nextAiringEpisode {
                        episode
                        airingAt
                        timeUntilAiring
                    }
                    externalLinks {
                        site
                        url
                        type
                        language
                    }
                }
            }
        }
        """

        response = requests.post(
            self.API_URL,
            json={
                "query": query,
                "variables": {
                    "search": search,
                    "perPage": per_page,
                },
            },
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"AniList API error {response.status_code}: {response.text}"
            )

        payload = response.json()

        if "errors" in payload:
            raise Exception(payload["errors"])

        return payload.get("data", {}).get("Page", {}).get("media", [])

    def fetch_seasonal_anime(self, season, season_year, page=1, per_page=50):
        query = """
        query ($season: MediaSeason, $seasonYear: Int, $page: Int, $perPage: Int) {
        Page(page: $page, perPage: $perPage) {
            pageInfo {
            currentPage
            hasNextPage
            lastPage
            total
            }
            media(
            season: $season,
            seasonYear: $seasonYear,
            type: ANIME,
            sort: POPULARITY_DESC
            ) {
            id
            idMal
            title {
                romaji
                english
                native
            }
            coverImage {
                large
                medium
            }
            season
            seasonYear
            format
            status
            episodes
            duration
            genres
            studios(isMain: true) {
                nodes {
                name
                }
            }
            nextAiringEpisode {
                episode
                airingAt
                timeUntilAiring
            }
            externalLinks {
                site
                url
                type
                language
            }
            }
        }
        }
        """

        variables = {
            "season": season.upper(),
            "seasonYear": season_year,
            "page": page,
            "perPage": per_page,
        }

        response = requests.post(
            self.API_URL,
            json={
                "query": query,
                "variables": variables,
            },
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"AniList API error {response.status_code}: {response.text}"
            )

        payload = response.json()

        if "errors" in payload:
            raise Exception(payload["errors"])

        return payload.get("data", {}).get("Page")
    
