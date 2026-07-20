from django.test import TestCase
from django.urls import reverse


class GameKirokuRouteTests(TestCase):
    def test_dashboard_is_public(self):
        response = self.client.get(
            reverse("games:dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "games/dashboard.html",
        )

    def test_dashboard_displays_module_identity(self):
        response = self.client.get(
            reverse("games:dashboard")
        )

        self.assertContains(
            response,
            "Game Kiroku",
        )
        self.assertContains(
            response,
            "ゲーム記録",
        )