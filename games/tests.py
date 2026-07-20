from decimal import Decimal
from datetime import date

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
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.WISHLIST,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        self.assertTrue(self.entry.is_owned)
        self.assertTrue(self.entry.is_wishlisted)

    def test_platform_rejects_values_outside_choices(self):
        access = GameAccess(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name="playstation_4",
            store=GameAccess.Store.PLAYSTATION_STORE,
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
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
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

    def test_playing_game_with_completed_history_counts_as_completed(
        self,
    ):
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )
        Playthrough.objects.create(
            library_entry=self.entry,
            number=1,
            status=Playthrough.Status.COMPLETED,
            text_language=Playthrough.TextLanguage.ENGLISH,
        )
        Playthrough.objects.create(
            library_entry=self.entry,
            number=2,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.JAPANESE,
        )

        response = self.client.get(
            reverse("games:dashboard")
        )

        self.assertEqual(
            response.context["completed_count"],
            1,
        )

        active_entry = response.context[
            "active_entries"
        ][0]

        self.assertTrue(
            active_entry.has_completed_history
        )

    def test_multiplayer_is_excluded_from_completion_ratio(
        self,
    ):
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        Playthrough.objects.create(
            library_entry=self.entry,
            number=1,
            status=Playthrough.Status.COMPLETED,
            text_language=Playthrough.TextLanguage.ENGLISH,
        )

        multiplayer_game = Game.objects.create(
            title="Rocket League",
        )
        multiplayer_entry = LibraryEntry.objects.create(
            game=multiplayer_game,
            status=LibraryEntry.Status.MULTIPLAYER,
        )
        GameAccess.objects.create(
            library_entry=multiplayer_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.EPIC_GAMES,
        )

        response = self.client.get(
            reverse("games:dashboard")
        )

        self.assertEqual(
            response.context["owned_count"],
            2,
        )
        self.assertEqual(
            response.context["completable_owned_count"],
            1,
        )
        self.assertEqual(
            response.context["completed_count"],
            1,
        )
        self.assertEqual(
            response.context["completion_ratio"],
            100,
        )

class GameKirokuLibraryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.yakuza = Game.objects.create(
            title="Yakuza Kiwami 2",
        )
        cls.yakuza_entry = LibraryEntry.objects.create(
            game=cls.yakuza,
            status=LibraryEntry.Status.PLAYING,
        )
        GameAccess.objects.create(
            library_entry=cls.yakuza_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )
        Playthrough.objects.create(
            library_entry=cls.yakuza_entry,
            number=1,
            status=Playthrough.Status.COMPLETED,
            text_language=Playthrough.TextLanguage.ENGLISH,
        )
        Playthrough.objects.create(
            library_entry=cls.yakuza_entry,
            number=2,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.JAPANESE,
        )

        cls.rocket_league = Game.objects.create(
            title="Rocket League",
        )
        cls.rocket_entry = LibraryEntry.objects.create(
            game=cls.rocket_league,
            status=LibraryEntry.Status.MULTIPLAYER,
        )
        GameAccess.objects.create(
            library_entry=cls.rocket_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.EPIC_GAMES,
        )

    def test_library_is_public(self):
        response = self.client.get(
            reverse("games:library")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "games/library.html",
        )

    def test_library_filters_by_search(self):
        response = self.client.get(
            reverse("games:library"),
            {"q": "Yakuza"},
        )

        self.assertContains(
            response,
            "Yakuza Kiwami 2",
        )
        self.assertNotContains(
            response,
            "Rocket League",
        )

    def test_completed_once_includes_replaying_game(self):
        response = self.client.get(
            reverse("games:library"),
            {"status": "completed_once"},
        )

        self.assertContains(
            response,
            "Yakuza Kiwami 2",
        )
        self.assertNotContains(
            response,
            "Rocket League",
        )

class GameKirokuDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.game = Game.objects.create(
            title="Yakuza Kiwami 2",
        )
        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.PLAYING,
        )

        cls.access = GameAccess.objects.create(
            library_entry=cls.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        Playthrough.objects.create(
            library_entry=cls.entry,
            access=cls.access,
            number=1,
            status=Playthrough.Status.COMPLETED,
            text_language=Playthrough.TextLanguage.ENGLISH,
            progress_note="Main Story completed",
        )

        Playthrough.objects.create(
            library_entry=cls.entry,
            access=cls.access,
            number=2,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.JAPANESE,
            progress_note="In progress",
        )

    def test_game_detail_is_public(self):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "games/detail.html",
        )
        self.assertContains(
            response,
            "Yakuza Kiwami 2",
        )

    def test_game_detail_displays_replay_history(self):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertContains(response, "Replaying")
        self.assertContains(response, "Playthrough 2")
        self.assertContains(response, "Japanese")
        self.assertContains(response, "Playthrough 1")
        self.assertContains(response, "English")

    def test_unknown_game_slug_returns_404(self):
        response = self.client.get(
            reverse(
                "games:detail",
                kwargs={
                    "slug": "unknown-game",
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_library_links_to_game_detail(self):
        response = self.client.get(
            reverse("games:library")
        )

        self.assertContains(
            response,
            self.game.get_absolute_url(),
        )

    def test_dashboard_links_to_game_detail(self):
        response = self.client.get(
            reverse("games:dashboard")
        )

        self.assertContains(
            response,
            self.game.get_absolute_url(),
        )

    def test_game_detail_displays_access_information(self):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertContains(response, "Owned")
        self.assertContains(response, "PC")
        self.assertContains(response, "Steam")

    def test_multiplayer_detail_does_not_expect_main_story_duration(self):
        multiplayer_game = Game.objects.create(
            title="Rocket League",
        )
        multiplayer_entry = LibraryEntry.objects.create(
            game=multiplayer_game,
            status=LibraryEntry.Status.MULTIPLAYER,
        )

        response = self.client.get(
            multiplayer_game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not Applicable")
        self.assertContains(
            response,
            "Persistent multiplayer games do not require a traditional playthrough.",
        )