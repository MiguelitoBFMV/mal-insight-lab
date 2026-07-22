import requests

from mal_data.services.mal_oauth import (
    get_valid_access_token,
)


class MyAnimeListClient:
    ANIME_LIST_URL = "https://api.myanimelist.net/v2/users/@me/animelist"
    MANGA_LIST_URL = "https://api.myanimelist.net/v2/users/@me/mangalist"
    ANIME_DETAIL_URL = "https://api.myanimelist.net/v2/anime/{anime_id}"
    ANIME_MY_LIST_STATUS_URL = "https://api.myanimelist.net/v2/anime/{anime_id}/my_list_status"

    def get_headers(self, *, force_refresh=False):
        access_token = get_valid_access_token(
            force_refresh=force_refresh,
        )

        return {
            "Authorization": f"Bearer {access_token}",
        }


    def _request(
        self,
        method,
        url,
        *,
        params=None,
        data=None,
    ):
        response = requests.request(
            method,
            url,
            headers=self.get_headers(),
            params=params,
            data=data,
            timeout=30,
        )

        if response.status_code == 401:
            response = requests.request(
                method,
                url,
                headers=self.get_headers(
                    force_refresh=True,
                ),
                params=params,
                data=data,
                timeout=30,
            )

        if not response.ok:
            raise Exception(
                "Error consultando MyAnimeList API. "
                f"Status: {response.status_code}. "
                f"Response: {response.text}"
            )

        if not response.content:
            return {}

        return response.json()


    def fetch_page(self, url, params=None):
        return self._request(
            "GET",
            url,
            params=params,
        )


    def put_page(self, url, data=None):
        return self._request(
            "PUT",
            url,
            data=data,
        )
    
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
        url = self.ANIME_DETAIL_URL.format(
            anime_id=anime_id,
        )

        anime_data = self.fetch_page(
            url,
            params={
                "fields": "my_list_status",
            },
        )

        return anime_data.get("my_list_status")
    
    def update_anime_my_list_status(
        self,
        anime_id,
        status,
        num_watched_episodes=0,
        score=0,
        is_rewatching=False,
    ):
        url = self.ANIME_MY_LIST_STATUS_URL.format(anime_id=anime_id)

        data = {
            "status": status,
            "num_watched_episodes": num_watched_episodes,
            "score": score,
            "is_rewatching": "true" if is_rewatching else "false",
        }

        return self.put_page(url, data=data)

