from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PlatformAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="test-owner",
        )

    def test_home_is_public(self):
        response = self.client.get(
            reverse("core:home")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "core/home.html",
        )

    def test_login_page_is_available(self):
        response = self.client.get(
            reverse("login")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "registration/login.html",
        )

    def test_authenticated_owner_can_open_home(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("core:home")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "test-owner",
        )