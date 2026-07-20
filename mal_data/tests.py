from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class MalInsightsPublicRouteTests(TestCase):
    def get_public_urls(self):
        return [
            reverse(
                "mal_insights:dashboard"
            ),
            reverse(
                "mal_insights:anime_status_list",
                kwargs={"status": "watching"},
            ),
            reverse(
                "mal_insights:anime_relations_detail",
                kwargs={"mal_id": 999999},
            ),
            reverse(
                "mal_insights:anime_search"
            ),
            reverse(
                "mal_insights:seasonal_board"
            ),
        ]

    def test_public_routes_are_available_without_login(self):
        for url in self.get_public_urls():
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    200,
                )


class MalInsightsProtectedRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="test-owner",
        )

    def get_protected_urls(self):
        return [
            reverse(
                "mal_insights:sync_anime_list"
            ),
            reverse(
                "mal_insights:sync_anime_relations",
                kwargs={"mal_id": 999999},
            ),
            reverse(
                "mal_insights:rescue_anime_from_search"
            ),
            reverse(
                "mal_insights:sync_seasonal_board"
            ),
            reverse(
                "mal_insights:add_seasonal_to_plan"
            ),
        ]

    def test_anonymous_get_requests_redirect_to_login(self):
        login_url = reverse("login")

        for url in self.get_protected_urls():
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    302,
                )
                self.assertTrue(
                    response.url.startswith(
                        f"{login_url}?next="
                    )
                )

    def test_anonymous_post_requests_redirect_to_login(self):
        login_url = reverse("login")

        for url in self.get_protected_urls():
            with self.subTest(url=url):
                response = self.client.post(url)

                self.assertEqual(
                    response.status_code,
                    302,
                )
                self.assertTrue(
                    response.url.startswith(
                        f"{login_url}?next="
                    )
                )

    def test_authenticated_get_requests_return_405(self):
        self.client.force_login(self.owner)

        for url in self.get_protected_urls():
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    405,
                )