import requests
from django.conf import settings


class MyAnimeListClient:
    ANIME_LIST_URL = "https://api.myanimelist.net/v2/users/@me/animelist"
    MANGA_LIST_URL = "https://api.myanimelist.net/v2/users/@me/mangalist"
    ANIME_DETAIL_URL = "https://api.myanimelist.net/v2/anime/{anime_id}"
    ANIME_MY_LIST_STATUS_URL = "https://api.myanimelist.net/v2/anime/{anime_id}/my_list_status"

    def __init__(self):
        self.access_token = settings.MAL_ACCESS_TOKEN

        if not self.access_token:
            raise ValueError("MAL_ACCESS_TOKEN no está configurado en .env")

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
        }

    def fetch_page(self, url, params=None):
        response = requests.get(
            url,
            headers=self.get_headers(),
            params=params,
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"Error consultando MAL API. "
                f"Status: {response.status_code}. Response: {response.text}"
            )

        return response.json()

    def fetch_all_anime_by_status(self, status):
        params = {
            "status": status,
            "sort": "list_updated_at",
            "limit": 100,
            "fields": ",".join([
                "list_status",
                "num_episodes",
                "media_type",
                "status",
                "start_date",
                "end_date",
                "main_picture",
                "alternative_titles",
            ]),
        }

        all_entries = []
        next_url = self.ANIME_LIST_URL
        page = 1

        while next_url:
            if page == 1:
                data = self.fetch_page(next_url, params=params)
            else:
                data = self.fetch_page(next_url)

            entries = data.get("data", [])
            all_entries.extend(entries)

            yield {
                "page": page,
                "entries": entries,
                "total_accumulated": len(all_entries),
            }

            paging = data.get("paging", {})
            next_url = paging.get("next")
            page += 1

    def fetch_all_manga_by_status(self, status):
        params = {
            "status": status,
            "sort": "list_updated_at",
            "limit": 100,
            "fields": ",".join([
                "list_status",
                "num_volumes",
                "num_chapters",
                "media_type",
                "status",
                "start_date",
                "end_date",
                "main_picture",
                "alternative_titles",
            ]),
        }

        all_entries = []
        next_url = self.MANGA_LIST_URL
        page = 1

        while next_url:
            if page == 1:
                data = self.fetch_page(next_url, params=params)
            else:
                data = self.fetch_page(next_url)

            entries = data.get("data", [])
            all_entries.extend(entries)

            yield {
                "page": page,
                "entries": entries,
                "total_accumulated": len(all_entries),
            }

            paging = data.get("paging", {})
            next_url = paging.get("next")
            page += 1

    def fetch_anime_details(self, anime_id):
        url = self.ANIME_DETAIL_URL.format(anime_id=anime_id)

        params = {
            "fields": ",".join([
                "id",
                "title",
                "main_picture",
                "media_type",
                "status",
                "num_episodes",
                "start_date",
                "end_date",
                "related_anime",
                "related_manga",
                "alternative_titles",
                "related_anime{node{id,title,main_picture,alternative_titles,media_type,status,num_episodes,start_date,end_date},relation_type,relation_type_formatted}",
                "related_manga{node{id,title,main_picture,media_type,status,num_chapters,num_volumes,start_date,end_date},relation_type,relation_type_formatted}",
            ]),
        }

        return self.fetch_page(url, params=params)
    
    def fetch_anime_my_list_status(self, anime_id):
        url = self.ANIME_MY_LIST_STATUS_URL.format(anime_id=anime_id)

        response = requests.get(
            url,
            headers=self.get_headers(),
            timeout=30,
        )

        if response.status_code == 404:
            return None

        if not response.ok:
            raise Exception(
                f"MyAnimeList API error {response.status_code}: {response.text}"
            )

        return response.json()