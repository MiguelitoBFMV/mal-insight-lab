from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from games.models import (
    Game,
    GameAccess,
    LibraryEntry,
    Playthrough,
)


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


class GameKirokuModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game = Game.objects.create(
            title="Yakuza Kiwami 2",
            igdb_main_story_hours=Decimal("18.50"),
        )
        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.PLAYING,
        )

    def test_effective_hours_use_igdb_by_default(self):
        self.assertEqual(
            self.entry.effective_main_story_hours,
            Decimal("18.50"),
        )

    def test_manual_hours_override_igdb_value(self):
        self.entry.main_story_hours_override = Decimal("20.00")

        self.assertEqual(
            self.entry.effective_main_story_hours,
            Decimal("20.00"),
        )

    def test_owned_and_wishlist_accesses_can_coexist(self):
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_family=GameAccess.PlatformFamily.PC,
            platform_name="PC",
            store="Steam",
        )
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.WISHLIST,
            platform_family=GameAccess.PlatformFamily.PLAYSTATION,
            platform_name="PS5",
            store="PlayStation Store",
        )

        self.assertTrue(self.entry.is_owned)
        self.assertTrue(self.entry.is_wishlisted)

    def test_wishlist_access_rejects_acquisition_date(self):
        access = GameAccess(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.WISHLIST,
            platform_family=GameAccess.PlatformFamily.PLAYSTATION,
            platform_name="PS5",
            acquired_on=date(2026, 7, 20),
        )

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_playthrough_rejects_invalid_date_range(self):
        playthrough = Playthrough(
            library_entry=self.entry,
            number=1,
            status=Playthrough.Status.COMPLETED,
            text_language=Playthrough.TextLanguage.JAPANESE,
            started_on=date(2026, 7, 20),
            finished_on=date(2026, 7, 19),
        )

        with self.assertRaises(ValidationError):
            playthrough.full_clean()

    def test_playthrough_access_must_match_library_entry(self):
        other_game = Game.objects.create(
            title="Final Fantasy VII",
        )
        other_entry = LibraryEntry.objects.create(
            game=other_game,
            status=LibraryEntry.Status.PLAYING,
        )
        other_access = GameAccess.objects.create(
            library_entry=other_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_family=GameAccess.PlatformFamily.PC,
            platform_name="PC",
            store="Steam",
        )

        playthrough = Playthrough(
            library_entry=self.entry,
            access=other_access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.JAPANESE,
        )

        with self.assertRaises(ValidationError):
            playthrough.full_clean()