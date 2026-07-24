from io import StringIO
from decimal import Decimal
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from games.forms import IGDBNewGameImportForm
from games.models import (
    CompetitiveMode,
    CompetitiveRankRecord,
    CompetitiveRankTier,
    Franchise,
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

    def test_platinum_date_requires_unlocked_platinum(self):
        self.entry.has_platinum = False
        self.entry.platinum_earned_on = date(
            2024,
            5,
            31,
        )

        with self.assertRaises(ValidationError):
            self.entry.full_clean()

    def test_unlocked_platinum_cannot_remain_target(self):
        self.entry.has_platinum = True
        self.entry.is_platinum_target = True

        with self.assertRaises(ValidationError):
            self.entry.full_clean()


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


class GameKirokuPlatinumTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dated_game = Game.objects.create(
            title="Dated Platinum",
        )
        cls.dated_entry = LibraryEntry.objects.create(
            game=cls.dated_game,
            status=LibraryEntry.Status.COMPLETED,
            has_platinum=True,
            platinum_earned_on=date(2024, 5, 31),
        )
        GameAccess.objects.create(
            library_entry=cls.dated_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        cls.older_game = Game.objects.create(
            title="Older Platinum",
        )
        cls.older_entry = LibraryEntry.objects.create(
            game=cls.older_game,
            status=LibraryEntry.Status.COMPLETED,
            has_platinum=True,
            platinum_earned_on=date(2018, 6, 18),
        )
        GameAccess.objects.create(
            library_entry=cls.older_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        cls.undated_game = Game.objects.create(
            title="Undated Platinum",
        )
        cls.undated_entry = LibraryEntry.objects.create(
            game=cls.undated_game,
            status=LibraryEntry.Status.COMPLETED,
            has_platinum=True,
        )
        GameAccess.objects.create(
            library_entry=cls.undated_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        cls.target_game = Game.objects.create(
            title="Platinum Target",
        )
        cls.target_entry = LibraryEntry.objects.create(
            game=cls.target_game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
            is_platinum_target=True,
        )
        GameAccess.objects.create(
            library_entry=cls.target_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

    def test_platinum_page_is_public(self):
        response = self.client.get(
            reverse("games:platinum")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "games/platinum.html",
        )

    def test_platinum_page_separates_collection_sections(self):
        response = self.client.get(
            reverse("games:platinum")
        )

        self.assertEqual(
            response.context["platinum_count"],
            3,
        )
        self.assertEqual(
            response.context["latest_platinum"],
            self.dated_entry,
        )
        self.assertIn(
            self.dated_entry,
            response.context["dated_platinums"],
        )
        self.assertIn(
            self.older_entry,
            response.context["dated_platinums"],
        )
        self.assertIn(
            self.undated_entry,
            response.context["undated_platinums"],
        )
        self.assertIn(
            self.target_entry,
            response.context["platinum_targets"],
        )

    def test_platinum_history_orders_newest_first(self):
        response = self.client.get(
            reverse("games:platinum")
        )

        dated_platinums = response.context[
            "dated_platinums"
        ]

        self.assertEqual(
            dated_platinums,
            [
                self.dated_entry,
                self.older_entry,
            ],
        )

    def test_library_filters_unlocked_platinums(self):
        response = self.client.get(
            reverse("games:library"),
            {
                "platinum": "unlocked",
            },
        )

        self.assertContains(
            response,
            "Dated Platinum",
        )
        self.assertContains(
            response,
            "Older Platinum",
        )
        self.assertContains(
            response,
            "Undated Platinum",
        )
        entries = list(
            response.context["entries"]
        )

        self.assertNotIn(
            self.target_entry,
            entries,
)

    def test_library_filters_platinum_targets(self):
        response = self.client.get(
            reverse("games:library"),
            {
                "platinum": "target",
            },
        )

        self.assertContains(
            response,
            "Platinum Target",
        )
        self.assertNotContains(
            response,
            "Dated Platinum",
        )

    def test_unlocked_filter_orders_dates_before_unknown(self):
        response = self.client.get(
            reverse("games:library"),
            {
                "platinum": "unlocked",
            },
        )

        entries = list(
            response.context["entries"]
        )

        self.assertEqual(
            entries,
            [
                self.dated_entry,
                self.older_entry,
                self.undated_entry,
            ],
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
        self.assertContains(
            response,
            "Not Applicable",
        )
        self.assertContains(
            response,
            "Persistent multiplayer games do not require",
        )
        self.assertContains(
            response,
            "playthrough.",
        )


class GameKirokuOwnerControlsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="game-owner",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="Owner Controls Game",
        )

        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

        cls.access = GameAccess.objects.create(
            library_entry=cls.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

    def test_owner_controls_are_hidden_from_anonymous_users(self):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'id="owner-controls-title"',
        )
        self.assertNotContains(
            response,
            "Save Library Entry",
        )

    def test_owner_controls_are_visible_to_authenticated_owner(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="owner-controls-title"',
        )
        self.assertContains(
            response,
            "Edit Library Entry",
        )
        self.assertContains(
            response,
            "Save Library Entry",
        )

    def test_anonymous_update_redirects_to_login(self):
        update_url = reverse(
            "games:update_entry",
            kwargs={
                "slug": self.game.slug,
            },
        )

        response = self.client.post(
            update_url,
            {
                "has_platinum": "on",
                "main_story_hours_override": "18.5",
                "notes": "Unauthorized update",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )

        self.entry.refresh_from_db()

        self.assertFalse(self.entry.has_platinum)
        self.assertIsNone(
            self.entry.main_story_hours_override
        )
        self.assertEqual(self.entry.notes, "")

    def test_authenticated_get_to_update_route_returns_405(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "games:update_entry",
                kwargs={
                    "slug": self.game.slug,
                },
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_authenticated_owner_can_update_library_entry(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_entry",
                kwargs={
                    "slug": self.game.slug,
                },
            ),
            {
                "status": (
                    LibraryEntry.Status.PLAN_TO_PLAY
                ),
                "has_platinum": "on",
                "main_story_hours_override": "18.5",
                "notes": "Priority replay candidate.",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.entry.refresh_from_db()

        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.PLAN_TO_PLAY,
        )
        self.assertTrue(self.entry.has_platinum)
        self.assertEqual(
            self.entry.main_story_hours_override,
            Decimal("18.5"),
        )
        self.assertEqual(
            self.entry.notes,
            "Priority replay candidate.",
        )

    def test_multiplayer_rejects_manual_main_story_duration(self):
        multiplayer_game = Game.objects.create(
            title="Persistent Multiplayer Game",
        )

        multiplayer_entry = LibraryEntry.objects.create(
            game=multiplayer_game,
            status=LibraryEntry.Status.MULTIPLAYER,
        )

        GameAccess.objects.create(
            library_entry=multiplayer_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_entry",
                kwargs={
                    "slug": multiplayer_game.slug,
                },
            ),
            {
                "status": (
                    LibraryEntry.Status.MULTIPLAYER
                ),
                "main_story_hours_override": "5",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                "Persistent multiplayer games do not use "
                "a main-story duration."
            ),
        )

        multiplayer_entry.refresh_from_db()

        self.assertIsNone(
            multiplayer_entry.main_story_hours_override
        )


class GameKirokuFranchiseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="franchise-owner",
            password="test-password",
        )

        cls.active_franchise = Franchise.objects.create(
            name="Assassin's Creed",
            description="A historical action series.",
            logo_url="https://example.com/ac-logo.png",
        )

        cls.empty_franchise = Franchise.objects.create(
            name="Persona",
            description="A Japanese role-playing series.",
        )

        cls.other_franchise = Franchise.objects.create(
            name="Yakuza / Like a Dragon",
        )

        cls.old_game = Game.objects.create(
            title="Assassin's Creed",
            first_release_date=date(
                2007,
                11,
                13,
            ),
            franchise=cls.active_franchise,
        )

        cls.old_entry = LibraryEntry.objects.create(
            game=cls.old_game,
            status=LibraryEntry.Status.COMPLETED,
        )

        GameAccess.objects.create(
            library_entry=cls.old_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        cls.new_game = Game.objects.create(
            title="Assassin's Creed Mirage",
            first_release_date=date(
                2023,
                10,
                5,
            ),
            franchise=cls.active_franchise,
        )

        cls.new_entry = LibraryEntry.objects.create(
            game=cls.new_game,
            status=LibraryEntry.Status.PLAYING,
        )

        cls.new_access = GameAccess.objects.create(
            library_entry=cls.new_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        Playthrough.objects.create(
            library_entry=cls.new_entry,
            access=cls.new_access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.ENGLISH,
        )

        cls.unassigned_game = Game.objects.create(
            title="Judgment",
            first_release_date=date(
                2018,
                12,
                13,
            ),
        )

        cls.unassigned_entry = (
            LibraryEntry.objects.create(
                game=cls.unassigned_game,
                status=(
                    LibraryEntry.Status.PLAN_TO_PLAY
                ),
            )
        )

        GameAccess.objects.create(
            library_entry=cls.unassigned_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

    def franchise_list_url(self):
        return reverse(
            "games:franchise_list"
        )

    def franchise_detail_url(
        self,
        franchise=None,
    ):
        selected_franchise = (
            franchise or self.active_franchise
        )

        return reverse(
            "games:franchise_detail",
            kwargs={
                "slug": selected_franchise.slug,
            },
        )

    def create_url(self):
        return reverse(
            "games:create_franchise"
        )

    def update_url(
        self,
        franchise=None,
    ):
        selected_franchise = (
            franchise or self.active_franchise
        )

        return reverse(
            "games:update_franchise",
            kwargs={
                "slug": selected_franchise.slug,
            },
        )

    def delete_url(
        self,
        franchise=None,
    ):
        selected_franchise = (
            franchise or self.empty_franchise
        )

        return reverse(
            "games:delete_franchise",
            kwargs={
                "slug": selected_franchise.slug,
            },
        )

    def assignment_url(
        self,
        game=None,
    ):
        selected_game = (
            game or self.unassigned_game
        )

        return reverse(
            "games:update_game_franchise",
            kwargs={
                "slug": selected_game.slug,
            },
        )

    def test_franchise_list_is_public(self):
        response = self.client.get(
            self.franchise_list_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "games/franchise_list.html",
        )

    def test_anonymous_list_excludes_empty_franchises(
        self,
    ):
        response = self.client.get(
            self.franchise_list_url()
        )

        franchises = list(
            response.context["franchises"]
        )

        self.assertIn(
            self.active_franchise,
            franchises,
        )
        self.assertNotIn(
            self.empty_franchise,
            franchises,
        )

    def test_owner_list_includes_empty_franchises(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.franchise_list_url()
        )

        franchises = list(
            response.context["franchises"]
        )

        self.assertIn(
            self.active_franchise,
            franchises,
        )
        self.assertIn(
            self.empty_franchise,
            franchises,
        )
        self.assertContains(
            response,
            "Add Franchise",
        )

    def test_franchise_detail_is_public(self):
        response = self.client.get(
            self.franchise_detail_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "games/franchise_detail.html",
        )
        self.assertContains(
            response,
            "Assassin&#x27;s Creed",
        )

    def test_owner_controls_are_hidden_from_anonymous_users(
        self,
    ):
        response = self.client.get(
            self.franchise_detail_url()
        )

        self.assertNotContains(
            response,
            "Edit Franchise",
        )
        self.assertNotContains(
            response,
            "Add Game",
        )
        self.assertNotContains(
            response,
            "Delete Franchise",
        )

    def test_owner_controls_and_add_game_are_visible(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.franchise_detail_url()
        )

        self.assertContains(
            response,
            "Edit Franchise",
        )
        self.assertContains(
            response,
            "Add Game",
        )
        self.assertContains(
            response,
            "Delete Franchise",
        )

    def test_anonymous_creation_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.create_url(),
            {
                "name": "Final Fantasy",
                "description": "",
                "logo_url": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse("login"),
            response.url,
        )
        self.assertFalse(
            Franchise.objects.filter(
                name="Final Fantasy",
            ).exists()
        )

    def test_authenticated_get_to_creation_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.create_url()
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_owner_can_create_franchise(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            {
                "name": "Final Fantasy",
                "description": (
                    "A long-running RPG anthology."
                ),
                "logo_url": (
                    "https://example.com/ff-logo.png"
                ),
            },
        )

        created_franchise = (
            Franchise.objects.get(
                name="Final Fantasy",
            )
        )

        self.assertRedirects(
            response,
            created_franchise.get_absolute_url(),
        )
        self.assertEqual(
            created_franchise.description,
            "A long-running RPG anthology.",
        )
        self.assertEqual(
            created_franchise.logo_url,
            "https://example.com/ff-logo.png",
        )

    def test_owner_can_update_franchise(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.update_url(),
            {
                "franchise-name": (
                    "Assassin's Creed"
                ),
                "franchise-description": (
                    "Updated franchise description."
                ),
                "franchise-logo_url": (
                    "https://example.com/new-logo.png"
                ),
            },
        )

        self.active_franchise.refresh_from_db()

        self.assertRedirects(
            response,
            self.active_franchise.get_absolute_url(),
        )
        self.assertEqual(
            self.active_franchise.description,
            "Updated franchise description.",
        )
        self.assertEqual(
            self.active_franchise.logo_url,
            "https://example.com/new-logo.png",
        )

    def test_empty_franchise_can_be_deleted(self):
        empty_franchise_pk = (
            self.empty_franchise.pk
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url()
        )

        self.assertRedirects(
            response,
            self.franchise_list_url(),
        )
        self.assertFalse(
            Franchise.objects.filter(
                pk=empty_franchise_pk,
            ).exists()
        )

    def test_franchise_with_games_cannot_be_deleted(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url(
                franchise=self.active_franchise,
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            (
                "A franchise with assigned games "
                "cannot be deleted."
            ),
        )
        self.assertTrue(
            Franchise.objects.filter(
                pk=self.active_franchise.pk,
            ).exists()
        )

    def test_authenticated_get_to_delete_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.delete_url()
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_owner_can_assign_game_to_franchise(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.assignment_url(),
            {
                "franchise-franchise": str(
                    self.active_franchise.pk
                ),
            },
        )

        self.assertRedirects(
            response,
            self.unassigned_game.get_absolute_url(),
        )

        self.unassigned_game.refresh_from_db()

        self.assertEqual(
            self.unassigned_game.franchise,
            self.active_franchise,
        )

    def test_owner_can_move_game_between_franchises(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.assignment_url(
                game=self.old_game,
            ),
            {
                "franchise-franchise": str(
                    self.other_franchise.pk
                ),
            },
        )

        self.assertRedirects(
            response,
            self.old_game.get_absolute_url(),
        )

        self.old_game.refresh_from_db()

        self.assertEqual(
            self.old_game.franchise,
            self.other_franchise,
        )

    def test_owner_can_remove_game_from_franchise(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.assignment_url(
                game=self.old_game,
            ),
            {
                "franchise-franchise": "",
            },
        )

        self.assertRedirects(
            response,
            self.old_game.get_absolute_url(),
        )

        self.old_game.refresh_from_db()

        self.assertIsNone(
            self.old_game.franchise
        )

    def test_anonymous_assignment_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.assignment_url(),
            {
                "franchise-franchise": str(
                    self.active_franchise.pk
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse("login"),
            response.url,
        )

        self.unassigned_game.refresh_from_db()

        self.assertIsNone(
            self.unassigned_game.franchise
        )

    def test_release_timeline_orders_oldest_first_by_default(
        self,
    ):
        response = self.client.get(
            self.franchise_detail_url()
        )

        entries = list(
            response.context["entries"]
        )

        self.assertEqual(
            entries,
            [
                self.old_entry,
                self.new_entry,
            ],
        )
        self.assertEqual(
            response.context["sort_order"],
            "asc",
        )

    def test_release_timeline_can_order_newest_first(
        self,
    ):
        response = self.client.get(
            self.franchise_detail_url(),
            {
                "sort": "desc",
            },
        )

        entries = list(
            response.context["entries"]
        )

        self.assertEqual(
            entries,
            [
                self.new_entry,
                self.old_entry,
            ],
        )
        self.assertEqual(
            response.context["sort_order"],
            "desc",
        )

    def test_invalid_sort_falls_back_to_oldest_first(
        self,
    ):
        response = self.client.get(
            self.franchise_detail_url(),
            {
                "sort": "something-invalid",
            },
        )

        entries = list(
            response.context["entries"]
        )

        self.assertEqual(
            entries,
            [
                self.old_entry,
                self.new_entry,
            ],
        )
        self.assertEqual(
            response.context["sort_order"],
            "asc",
        )

    def test_playing_game_has_representative_priority(
        self,
    ):
        response = self.client.get(
            self.franchise_detail_url()
        )

        self.assertEqual(
            response.context[
                "representative_game"
            ],
            self.new_game,
        )
        self.assertEqual(
            response.context[
                "representative_label"
            ],
            "Currently Playing",
        )

        list_response = self.client.get(
            self.franchise_list_url()
        )

        rendered_franchise = next(
            franchise
            for franchise
            in list_response.context[
                "franchises"
            ]
            if (
                franchise.pk
                == self.active_franchise.pk
            )
        )

        self.assertEqual(
            rendered_franchise.representative_game,
            self.new_game,
        )

    def test_import_form_accepts_existing_franchise(
        self,
    ):
        form = IGDBNewGameImportForm(
            data={
                "status": (
                    LibraryEntry.Status.PLAN_TO_PLAY
                ),
                "franchise": str(
                    self.active_franchise.pk
                ),
                "access_type": (
                    GameAccess.AccessType.WISHLIST
                ),
                "platform_name": (
                    GameAccess.Platform.PLAYSTATION_5
                ),
                "store": (
                    GameAccess.Store.PLAYSTATION_STORE
                ),
                "notes": "",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )
        self.assertEqual(
            form.cleaned_data["franchise"],
            self.active_franchise,
        )


class GameKirokuPlaythroughActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="playthrough-owner",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="Playthrough Action Game",
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

        cls.playthrough = Playthrough.objects.create(
            library_entry=cls.entry,
            access=cls.access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.ENGLISH,
            progress_note="In progress",
        )

    def action_url(self, playthrough=None):
        selected_playthrough = (
            playthrough or self.playthrough
        )

        return reverse(
            "games:update_playthrough_state",
            kwargs={
                "slug": self.game.slug,
                "playthrough_id": (
                    selected_playthrough.pk
                ),
            },
        )

    def test_anonymous_action_redirects_to_login(self):
        response = self.client.post(
            self.action_url(),
            {
                "action": "pause",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )

        self.playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        self.assertEqual(
            self.playthrough.status,
            Playthrough.Status.PLAYING,
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.PLAYING,
        )

    def test_authenticated_get_to_action_route_returns_405(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.action_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_pause_synchronizes_playthrough_and_library_entry(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.action_url(),
            {
                "action": "pause",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        self.assertEqual(
            self.playthrough.status,
            Playthrough.Status.PAUSED,
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.PAUSED,
        )

    def test_resume_pauses_another_active_playthrough(self):
        self.playthrough.status = (
            Playthrough.Status.PAUSED
        )
        self.playthrough.save(
            update_fields=["status"]
        )

        self.entry.status = LibraryEntry.Status.PAUSED
        self.entry.save(
            update_fields=["status"]
        )

        other_playthrough = Playthrough.objects.create(
            library_entry=self.entry,
            access=self.access,
            number=2,
            status=Playthrough.Status.PLAYING,
            text_language=(
                Playthrough.TextLanguage.JAPANESE
            ),
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.action_url(),
            {
                "action": "resume",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.playthrough.refresh_from_db()
        other_playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        self.assertEqual(
            self.playthrough.status,
            Playthrough.Status.PLAYING,
        )
        self.assertEqual(
            other_playthrough.status,
            Playthrough.Status.PAUSED,
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.PLAYING,
        )
        self.assertIsNotNone(
            self.playthrough.started_on
        )

    def test_complete_sets_finished_date_and_completed_status(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.action_url(),
            {
                "action": "complete",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        self.assertEqual(
            self.playthrough.status,
            Playthrough.Status.COMPLETED,
        )
        self.assertEqual(
            self.playthrough.finished_on,
            timezone.localdate(),
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.COMPLETED,
        )

    def test_drop_synchronizes_playthrough_and_library_entry(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.action_url(),
            {
                "action": "drop",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        self.assertEqual(
            self.playthrough.status,
            Playthrough.Status.DROPPED,
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.DROPPED,
        )

    def test_invalid_transition_returns_400_without_changes(self):
        self.playthrough.status = (
            Playthrough.Status.COMPLETED
        )
        self.playthrough.save(
            update_fields=["status"]
        )

        self.entry.status = (
            LibraryEntry.Status.COMPLETED
        )
        self.entry.save(
            update_fields=["status"]
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.action_url(),
            {
                "action": "pause",
            },
        )

        self.assertEqual(response.status_code, 400)

        self.playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        self.assertEqual(
            self.playthrough.status,
            Playthrough.Status.COMPLETED,
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.COMPLETED,
        )

    def test_action_rejects_playthrough_from_another_entry(self):
        other_game = Game.objects.create(
            title="Different Game",
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

        other_playthrough = Playthrough.objects.create(
            library_entry=other_entry,
            access=other_access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=(
                Playthrough.TextLanguage.ENGLISH
            ),
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_playthrough_state",
                kwargs={
                    "slug": self.game.slug,
                    "playthrough_id": (
                        other_playthrough.pk
                    ),
                },
            ),
            {
                "action": "pause",
            },
        )

        self.assertEqual(response.status_code, 404)

        other_playthrough.refresh_from_db()

        self.assertEqual(
            other_playthrough.status,
            Playthrough.Status.PLAYING,
        )


class GameKirokuPlaythroughEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="playthrough-editor-owner",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="Playthrough Editor Game",
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

        cls.playthrough = Playthrough.objects.create(
            library_entry=cls.entry,
            access=cls.access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.ENGLISH,
            progress_note="In progress",
        )

    def update_url(self, playthrough=None):
        selected_playthrough = (
            playthrough or self.playthrough
        )

        return reverse(
            "games:update_playthrough",
            kwargs={
                "slug": self.game.slug,
                "playthrough_id": (
                    selected_playthrough.pk
                ),
            },
        )

    def form_data(self, **overrides):
        prefix = (
            f"playthrough-{self.playthrough.pk}"
        )

        data = {
            f"{prefix}-access": str(
                self.access.pk
            ),
            f"{prefix}-text_language": (
                Playthrough.TextLanguage.JAPANESE
            ),
            f"{prefix}-progress_note": "Chapter 10",
            f"{prefix}-started_on": "2026-07-20",
            f"{prefix}-finished_on": "",
            f"{prefix}-hours_played": "18",
            f"{prefix}-notes": "Hard but fun",
        }

        data.update(overrides)

        return data

    def test_editor_is_hidden_from_anonymous_users(self):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        field_id = (
            f'id="id_playthrough-'
            f'{self.playthrough.pk}-progress_note"'
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            field_id,
        )
        self.assertNotContains(
            response,
            "Save Playthrough Details",
        )

    def test_editor_is_visible_to_authenticated_owner(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        field_id = (
            f'id="id_playthrough-'
            f'{self.playthrough.pk}-progress_note"'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            field_id,
        )
        self.assertContains(
            response,
            "Edit Playthrough Details",
        )
        self.assertContains(
            response,
            "Save Playthrough Details",
        )

    def test_anonymous_update_redirects_to_login(self):
        response = self.client.post(
            self.update_url(),
            self.form_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )

        self.playthrough.refresh_from_db()

        self.assertEqual(
            self.playthrough.progress_note,
            "In progress",
        )
        self.assertEqual(
            self.playthrough.text_language,
            Playthrough.TextLanguage.ENGLISH,
        )

    def test_authenticated_get_to_update_route_returns_405(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.update_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_owner_can_update_playthrough_details(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.update_url(),
            self.form_data(),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.playthrough.refresh_from_db()

        self.assertEqual(
            self.playthrough.access,
            self.access,
        )
        self.assertEqual(
            self.playthrough.text_language,
            Playthrough.TextLanguage.JAPANESE,
        )
        self.assertEqual(
            self.playthrough.progress_note,
            "Chapter 10",
        )
        self.assertEqual(
            self.playthrough.started_on,
            date(2026, 7, 20),
        )
        self.assertIsNone(
            self.playthrough.finished_on
        )
        self.assertEqual(
            self.playthrough.hours_played,
            Decimal("18"),
        )
        self.assertEqual(
            self.playthrough.notes,
            "Hard but fun",
        )

    def test_active_playthrough_rejects_finish_date(self):
        self.client.force_login(self.owner)

        prefix = (
            f"playthrough-{self.playthrough.pk}"
        )

        response = self.client.post(
            self.update_url(),
            self.form_data(
                **{
                    f"{prefix}-finished_on":
                        "2026-07-21",
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                "An active or paused playthrough "
                "cannot have a finish date."
            ),
        )

        self.playthrough.refresh_from_db()

        self.assertIsNone(
            self.playthrough.finished_on
        )
        self.assertEqual(
            self.playthrough.progress_note,
            "In progress",
        )

    def test_completed_playthrough_accepts_finish_date(self):
        self.playthrough.status = (
            Playthrough.Status.COMPLETED
        )
        self.playthrough.save(
            update_fields=["status"]
        )

        self.entry.status = (
            LibraryEntry.Status.COMPLETED
        )
        self.entry.save(
            update_fields=["status"]
        )

        self.client.force_login(self.owner)

        prefix = (
            f"playthrough-{self.playthrough.pk}"
        )

        response = self.client.post(
            self.update_url(),
            self.form_data(
                **{
                    f"{prefix}-finished_on":
                        "2026-07-21",
                }
            ),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.playthrough.refresh_from_db()

        self.assertEqual(
            self.playthrough.finished_on,
            date(2026, 7, 21),
        )

    def test_editor_rejects_access_from_another_game(self):
        other_game = Game.objects.create(
            title="Other Access Game",
        )

        other_entry = LibraryEntry.objects.create(
            game=other_game,
            status=LibraryEntry.Status.PLAYING,
        )

        other_access = GameAccess.objects.create(
            library_entry=other_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        self.client.force_login(self.owner)

        prefix = (
            f"playthrough-{self.playthrough.pk}"
        )

        response = self.client.post(
            self.update_url(),
            self.form_data(
                **{
                    f"{prefix}-access":
                        str(other_access.pk),
                }
            ),
        )

        self.assertEqual(response.status_code, 200)

        rendered_playthrough = next(
            playthrough
            for playthrough
            in response.context["entry"].detail_playthroughs
            if playthrough.pk == self.playthrough.pk
        )

        access_errors = (
            rendered_playthrough
            .owner_form
            .errors
            .as_data()
            .get("access", [])
        )

        self.assertTrue(access_errors)
        self.assertEqual(
            access_errors[0].code,
            "invalid_choice",
        )

        self.playthrough.refresh_from_db()

        self.assertEqual(
            self.playthrough.access,
            self.access,
        )

    def test_update_rejects_playthrough_from_another_entry(self):
        other_game = Game.objects.create(
            title="Other Playthrough Game",
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

        other_playthrough = Playthrough.objects.create(
            library_entry=other_entry,
            access=other_access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=(
                Playthrough.TextLanguage.ENGLISH
            ),
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_playthrough",
                kwargs={
                    "slug": self.game.slug,
                    "playthrough_id": (
                        other_playthrough.pk
                    ),
                },
            ),
            {},
        )

        self.assertEqual(response.status_code, 404)

        other_playthrough.refresh_from_db()

        self.assertEqual(
            other_playthrough.status,
            Playthrough.Status.PLAYING,
        )


class GameKirokuNewPlaythroughTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="new-playthrough-owner",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="New Playthrough Game",
        )

        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.COMPLETED,
        )

        cls.access = GameAccess.objects.create(
            library_entry=cls.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        cls.completed_playthrough = (
            Playthrough.objects.create(
                library_entry=cls.entry,
                access=cls.access,
                number=1,
                status=Playthrough.Status.COMPLETED,
                text_language=(
                    Playthrough.TextLanguage.ENGLISH
                ),
                progress_note="Main Story completed",
                finished_on=date(2026, 7, 1),
            )
        )

    def create_url(self, game=None):
        selected_game = game or self.game

        return reverse(
            "games:create_playthrough",
            kwargs={
                "slug": selected_game.slug,
            },
        )

    def form_data(
        self,
        *,
        access=None,
        started_on="",
        **overrides,
    ):
        selected_access = access or self.access

        data = {
            "new-playthrough-access": str(
                selected_access.pk
            ),
            "new-playthrough-text_language": (
                Playthrough.TextLanguage.JAPANESE
            ),
            "new-playthrough-progress_note": (
                "Fresh start"
            ),
            "new-playthrough-started_on": (
                started_on
            ),
            "new-playthrough-notes": (
                "Japanese replay."
            ),
        }

        data.update(overrides)

        return data

    def test_new_playthrough_form_is_hidden_from_anonymous_users(
        self,
    ):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'id="id_new-playthrough-access"',
        )
        self.assertNotContains(
            response,
            "Start Playthrough",
        )

    def test_new_playthrough_form_is_visible_to_owner(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="id_new-playthrough-access"',
        )
        self.assertContains(
            response,
            "Start New Playthrough",
        )
        self.assertContains(
            response,
            "Start Playthrough",
        )

    def test_multiplayer_does_not_display_creation_form(
        self,
    ):
        multiplayer_game = Game.objects.create(
            title="Multiplayer Without Runs",
        )

        LibraryEntry.objects.create(
            game=multiplayer_game,
            status=LibraryEntry.Status.MULTIPLAYER,
        )

        self.client.force_login(self.owner)

        response = self.client.get(
            multiplayer_game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'id="id_new-playthrough-access"',
        )
        self.assertNotContains(
            response,
            "Start Playthrough",
        )

    def test_anonymous_creation_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.create_url(),
            self.form_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )

        self.assertEqual(
            self.entry.playthroughs.count(),
            1,
        )

    def test_authenticated_get_to_creation_route_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.create_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_owner_can_start_next_numbered_playthrough(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.entry.refresh_from_db()

        created_playthrough = (
            self.entry.playthroughs.get(number=2)
        )

        self.assertEqual(
            created_playthrough.status,
            Playthrough.Status.PLAYING,
        )
        self.assertEqual(
            created_playthrough.access,
            self.access,
        )
        self.assertEqual(
            created_playthrough.text_language,
            Playthrough.TextLanguage.JAPANESE,
        )
        self.assertEqual(
            created_playthrough.progress_note,
            "Fresh start",
        )
        self.assertEqual(
            created_playthrough.started_on,
            timezone.localdate(),
        )
        self.assertEqual(
            created_playthrough.notes,
            "Japanese replay.",
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.PLAYING,
        )

        detail_response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertContains(
            detail_response,
            "Replaying",
        )

    def test_creation_uses_explicit_started_date(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(
                started_on="2026-07-15",
            ),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        created_playthrough = (
            self.entry.playthroughs.get(number=2)
        )

        self.assertEqual(
            created_playthrough.started_on,
            date(2026, 7, 15),
        )

    def test_starting_new_run_pauses_previous_active_run(
        self,
    ):
        active_playthrough = (
            Playthrough.objects.create(
                library_entry=self.entry,
                access=self.access,
                number=2,
                status=Playthrough.Status.PLAYING,
                text_language=(
                    Playthrough.TextLanguage.ENGLISH
                ),
            )
        )

        self.entry.status = (
            LibraryEntry.Status.PLAYING
        )
        self.entry.save(
            update_fields=["status"]
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        active_playthrough.refresh_from_db()
        self.entry.refresh_from_db()

        new_playthrough = (
            self.entry.playthroughs.get(number=3)
        )

        self.assertEqual(
            active_playthrough.status,
            Playthrough.Status.PAUSED,
        )
        self.assertEqual(
            new_playthrough.status,
            Playthrough.Status.PLAYING,
        )
        self.assertEqual(
            self.entry.status,
            LibraryEntry.Status.PLAYING,
        )

    def test_access_selector_only_contains_owned_accesses_for_entry(
        self,
    ):
        wishlist_access = GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.WISHLIST,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        other_game = Game.objects.create(
            title="Other New Run Game",
        )

        other_entry = LibraryEntry.objects.create(
            game=other_game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

        other_access = GameAccess.objects.create(
            library_entry=other_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        access_queryset = (
            response.context[
                "new_playthrough_form"
            ]
            .fields["access"]
            .queryset
        )

        self.assertIn(
            self.access,
            access_queryset,
        )
        self.assertNotIn(
            wishlist_access,
            access_queryset,
        )
        self.assertNotIn(
            other_access,
            access_queryset,
        )

    def test_creation_rejects_access_from_another_game(
        self,
    ):
        other_game = Game.objects.create(
            title="Foreign Access Game",
        )

        other_entry = LibraryEntry.objects.create(
            game=other_game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

        other_access = GameAccess.objects.create(
            library_entry=other_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(
                access=other_access,
            ),
        )

        self.assertEqual(response.status_code, 200)

        form = response.context[
            "new_playthrough_form"
        ]

        access_errors = (
            form.errors
            .as_data()
            .get("access", [])
        )

        self.assertTrue(access_errors)
        self.assertEqual(
            access_errors[0].code,
            "invalid_choice",
        )
        self.assertEqual(
            self.entry.playthroughs.count(),
            1,
        )

    def test_direct_multiplayer_creation_is_rejected(
        self,
    ):
        multiplayer_game = Game.objects.create(
            title="Protected Multiplayer Game",
        )

        multiplayer_entry = (
            LibraryEntry.objects.create(
                game=multiplayer_game,
                status=(
                    LibraryEntry.Status.MULTIPLAYER
                ),
            )
        )

        multiplayer_access = (
            GameAccess.objects.create(
                library_entry=multiplayer_entry,
                access_type=(
                    GameAccess.AccessType.OWNED
                ),
                platform_name=(
                    GameAccess.Platform.PC
                ),
                store=GameAccess.Store.STEAM,
            )
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(
                game=multiplayer_game,
            ),
            self.form_data(
                access=multiplayer_access,
            ),
        )

        self.assertEqual(response.status_code, 200)

        form = response.context[
            "new_playthrough_form"
        ]

        self.assertTrue(
            form.non_field_errors()
        )
        self.assertEqual(
            multiplayer_entry.playthroughs.count(),
            0,
        )


class GameKirokuAccessCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="access-owner",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="Access Creation Game",
        )

        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

    def create_url(self):
        return reverse(
            "games:create_access",
            kwargs={
                "slug": self.game.slug,
            },
        )

    def form_data(self, **overrides):
        data = {
            "new-access-access_type": (
                GameAccess.AccessType.OWNED
            ),
            "new-access-platform_name": (
                GameAccess.Platform.PLAYSTATION_5
            ),
            "new-access-store": (
                GameAccess.Store.PLAYSTATION_STORE
            ),
            "new-access-notes": (
                "Primary console copy."
            ),
        }

        data.update(overrides)

        return data

    def test_access_creator_is_hidden_from_anonymous_users(
        self,
    ):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'id="id_new-access-access_type"',
        )
        self.assertNotContains(
            response,
            "Add Library Access",
        )

    def test_access_creator_is_visible_to_owner(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="id_new-access-access_type"',
        )
        self.assertContains(
            response,
            "Add Platform or Store Access",
        )
        self.assertContains(
            response,
            "Add Library Access",
        )

    def test_anonymous_creation_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.create_url(),
            self.form_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )
        self.assertEqual(
            self.entry.accesses.count(),
            0,
        )

    def test_authenticated_get_to_creation_route_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.create_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_owner_can_create_owned_access(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        access = self.entry.accesses.get()

        self.assertEqual(
            access.access_type,
            GameAccess.AccessType.OWNED,
        )
        self.assertEqual(
            access.platform_name,
            GameAccess.Platform.PLAYSTATION_5,
        )
        self.assertEqual(
            access.store,
            GameAccess.Store.PLAYSTATION_STORE,
        )
        self.assertEqual(
            access.notes,
            "Primary console copy.",
        )

    def test_owner_can_create_wishlist_access(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(
                **{
                    "new-access-access_type":
                        GameAccess.AccessType.WISHLIST,
                    "new-access-platform_name":
                        GameAccess.Platform.PC,
                    "new-access-store":
                        GameAccess.Store.STEAM,
                    "new-access-notes":
                        "Wait for a discount.",
                }
            ),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        access = self.entry.accesses.get()

        self.assertEqual(
            access.access_type,
            GameAccess.AccessType.WISHLIST,
        )
        self.assertEqual(
            access.platform_name,
            GameAccess.Platform.PC,
        )
        self.assertEqual(
            access.store,
            GameAccess.Store.STEAM,
        )

    def test_owned_and_wishlist_access_can_share_location(
        self,
    ):
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(
                **{
                    "new-access-access_type":
                        GameAccess.AccessType.WISHLIST,
                    "new-access-platform_name":
                        GameAccess.Platform.PC,
                    "new-access-store":
                        GameAccess.Store.STEAM,
                }
            ),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )
        self.assertEqual(
            self.entry.accesses.count(),
            2,
        )

    def test_exact_duplicate_access_is_rejected(
        self,
    ):
        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(),
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["new_access_form"]

        self.assertTrue(
            form.non_field_errors()
        )
        self.assertEqual(
            self.entry.accesses.count(),
            1,
        )

    def test_invalid_platform_choice_is_rejected(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url(),
            self.form_data(
                **{
                    "new-access-platform_name":
                        "imaginary_console",
                }
            ),
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["new_access_form"]

        platform_errors = (
            form.errors
            .as_data()
            .get("platform_name", [])
        )

        self.assertTrue(platform_errors)
        self.assertEqual(
            platform_errors[0].code,
            "invalid_choice",
        )
        self.assertEqual(
            self.entry.accesses.count(),
            0,
        )


class GameKirokuAccessManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="access-manager",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="Access Management Game",
        )

        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.PLAYING,
        )

        cls.used_access = GameAccess.objects.create(
            library_entry=cls.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PLAYSTATION_5,
            store=GameAccess.Store.PLAYSTATION_STORE,
        )

        cls.playthrough = Playthrough.objects.create(
            library_entry=cls.entry,
            access=cls.used_access,
            number=1,
            status=Playthrough.Status.PLAYING,
            text_language=Playthrough.TextLanguage.ENGLISH,
        )

    def update_url(self, access=None):
        selected_access = access or self.used_access

        return reverse(
            "games:update_access",
            kwargs={
                "slug": self.game.slug,
                "access_id": selected_access.pk,
            },
        )

    def delete_url(self, access=None):
        selected_access = access or self.used_access

        return reverse(
            "games:delete_access",
            kwargs={
                "slug": self.game.slug,
                "access_id": selected_access.pk,
            },
        )

    def form_data(
        self,
        access=None,
        **overrides,
    ):
        selected_access = access or self.used_access
        prefix = f"access-{selected_access.pk}"

        data = {
            f"{prefix}-access_type": (
                selected_access.access_type
            ),
            f"{prefix}-platform_name": (
                selected_access.platform_name
            ),
            f"{prefix}-store": selected_access.store,
            f"{prefix}-notes": "Updated access notes.",
        }

        data.update(overrides)

        return data

    def test_access_manager_is_hidden_from_anonymous_users(
        self,
    ):
        response = self.client.get(
            self.game.get_absolute_url()
        )

        field_id = (
            f'id="id_access-'
            f'{self.used_access.pk}-access_type"'
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, field_id)
        self.assertNotContains(
            response,
            "Save Access",
        )
        self.assertNotContains(
            response,
            "Delete Access",
        )

    def test_access_manager_is_visible_to_owner(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        field_id = (
            f'id="id_access-'
            f'{self.used_access.pk}-access_type"'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, field_id)
        self.assertContains(
            response,
            "Manage Access",
        )
        self.assertContains(
            response,
            "Save Access",
        )
        self.assertContains(
            response,
            "Delete Access",
        )

    def test_anonymous_update_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.update_url(),
            self.form_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )

        self.used_access.refresh_from_db()

        self.assertEqual(
            self.used_access.notes,
            "",
        )

    def test_authenticated_get_to_update_route_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.update_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_owner_can_update_access_notes(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.update_url(),
            self.form_data(),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.used_access.refresh_from_db()

        self.assertEqual(
            self.used_access.notes,
            "Updated access notes.",
        )

    def test_update_rejects_exact_duplicate_access(
        self,
    ):
        editable_access = GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.WISHLIST,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        prefix = f"access-{editable_access.pk}"

        response = self.client.post(
            self.update_url(
                access=editable_access,
            ),
            self.form_data(
                access=editable_access,
                **{
                    f"{prefix}-access_type":
                        GameAccess.AccessType.WISHLIST,
                    f"{prefix}-platform_name":
                        GameAccess.Platform.PC,
                    f"{prefix}-store":
                        GameAccess.Store.STEAM,
                }
            ),
        )

        self.assertEqual(response.status_code, 200)

        rendered_access = next(
            access
            for access
            in response.context["entry"].detail_accesses
            if access.pk == editable_access.pk
        )

        self.assertTrue(
            rendered_access.owner_form.non_field_errors()
        )

        editable_access.refresh_from_db()

        self.assertEqual(
            editable_access.access_type,
            GameAccess.AccessType.OWNED,
        )
        self.assertEqual(
            editable_access.platform_name,
            GameAccess.Platform.PC,
        )
        self.assertEqual(
            editable_access.store,
            GameAccess.Store.STEAM,
        )

    def test_access_used_by_playthrough_must_remain_owned(
        self,
    ):
        self.client.force_login(self.owner)

        prefix = f"access-{self.used_access.pk}"

        response = self.client.post(
            self.update_url(),
            self.form_data(
                **{
                    f"{prefix}-access_type":
                        GameAccess.AccessType.WISHLIST,
                }
            ),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.used_access.refresh_from_db()

        self.assertEqual(
            self.used_access.access_type,
            GameAccess.AccessType.OWNED,
        )

    def test_anonymous_delete_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.delete_url()
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )
        self.assertTrue(
            GameAccess.objects.filter(
                pk=self.used_access.pk
            ).exists()
        )

    def test_authenticated_get_to_delete_route_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.delete_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_access_used_by_playthrough_cannot_be_deleted(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url()
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(
            response,
            (
                "This access is used by one or more "
                "playthroughs and cannot be deleted."
            ),
            status_code=409,
        )
        self.assertTrue(
            GameAccess.objects.filter(
                pk=self.used_access.pk
            ).exists()
        )

    def test_unused_access_can_be_deleted(
        self,
    ):
        unused_access = GameAccess.objects.create(
            library_entry=self.entry,
            access_type=GameAccess.AccessType.WISHLIST,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_url(
                access=unused_access,
            )
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )
        self.assertFalse(
            GameAccess.objects.filter(
                pk=unused_access.pk
            ).exists()
        )

    def test_update_rejects_access_from_another_entry(
        self,
    ):
        other_game = Game.objects.create(
            title="Foreign Managed Access Game",
        )

        other_entry = LibraryEntry.objects.create(
            game=other_game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

        other_access = GameAccess.objects.create(
            library_entry=other_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_access",
                kwargs={
                    "slug": self.game.slug,
                    "access_id": other_access.pk,
                },
            ),
            {},
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_rejects_access_from_another_entry(
        self,
    ):
        other_game = Game.objects.create(
            title="Foreign Deleted Access Game",
        )

        other_entry = LibraryEntry.objects.create(
            game=other_game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

        other_access = GameAccess.objects.create(
            library_entry=other_entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.STEAM,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:delete_access",
                kwargs={
                    "slug": self.game.slug,
                    "access_id": other_access.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            GameAccess.objects.filter(
                pk=other_access.pk
            ).exists()
        )

    def test_access_identity_is_locked_when_used_by_playthrough(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.game.get_absolute_url()
        )

        rendered_access = next(
            access
            for access
            in response.context["entry"].detail_accesses
            if access.pk == self.used_access.pk
        )

        form = rendered_access.owner_form

        self.assertTrue(
            form.fields["access_type"].disabled
        )
        self.assertTrue(
            form.fields["platform_name"].disabled
        )
        self.assertTrue(
            form.fields["store"].disabled
        )
        self.assertContains(
            response,
            (
                "Platform, store and access type are "
                "locked because"
            ),
        )

    def test_direct_post_cannot_rewrite_used_access_identity(
        self,
    ):
        self.client.force_login(self.owner)

        prefix = f"access-{self.used_access.pk}"

        response = self.client.post(
            self.update_url(),
            self.form_data(
                **{
                    f"{prefix}-access_type":
                        GameAccess.AccessType.WISHLIST,
                    f"{prefix}-platform_name":
                        GameAccess.Platform.PC,
                    f"{prefix}-store":
                        GameAccess.Store.STEAM,
                    f"{prefix}-notes":
                        "Notes remain editable.",
                }
            ),
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.used_access.refresh_from_db()

        self.assertEqual(
            self.used_access.access_type,
            GameAccess.AccessType.OWNED,
        )
        self.assertEqual(
            self.used_access.platform_name,
            GameAccess.Platform.PLAYSTATION_5,
        )
        self.assertEqual(
            self.used_access.store,
            GameAccess.Store.PLAYSTATION_STORE,
        )
        self.assertEqual(
            self.used_access.notes,
            "Notes remain editable.",
        )


class GameKirokuCompletedImportTests(TestCase):
    def create_completed_entry(
        self,
        *,
        title="Historical Completed Game",
    ):
        game = Game.objects.create(
            title=title,
        )

        entry = LibraryEntry.objects.create(
            game=game,
            status=LibraryEntry.Status.COMPLETED,
        )

        access = GameAccess.objects.create(
            library_entry=entry,
            access_type=GameAccess.AccessType.OWNED,
            platform_name=GameAccess.Platform.PC,
            store=GameAccess.Store.XBOX,
        )

        return entry, access

    def test_unspecified_language_is_available(self):
        choice_values = {
            value
            for value, _label
            in Playthrough.TextLanguage.choices
        }

        self.assertIn(
            Playthrough.TextLanguage.UNSPECIFIED,
            choice_values,
        )

    def test_xbox_game_pass_store_is_available(self):
        choice_values = {
            value
            for value, _label
            in GameAccess.Store.choices
        }

        self.assertIn(
            GameAccess.Store.XBOX,
            choice_values,
        )

    def test_completed_import_form_keeps_playthrough_data(
        self,
    ):
        form = IGDBNewGameImportForm(
            data={
                "status": (
                    LibraryEntry.Status.COMPLETED
                ),
                "franchise": "",
                "completed_text_language": (
                    Playthrough.TextLanguage.SPANISH
                ),
                "completed_on": "2026-07-23",
                "has_platinum": "",
                "platinum_earned_on": "",
                "is_platinum_target": "",
                "access_type": (
                    GameAccess.AccessType.OWNED
                ),
                "platform_name": (
                    GameAccess.Platform.PC
                ),
                "store": GameAccess.Store.XBOX,
                "notes": "",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

        self.assertEqual(
            form.cleaned_data[
                "completed_text_language"
            ],
            Playthrough.TextLanguage.SPANISH,
        )

        self.assertEqual(
            form.cleaned_data["completed_on"],
            date(2026, 7, 23),
        )

    def test_non_completed_import_discards_playthrough_data(
        self,
    ):
        form = IGDBNewGameImportForm(
            data={
                "status": (
                    LibraryEntry.Status.PLAN_TO_PLAY
                ),
                "franchise": "",
                "completed_text_language": (
                    Playthrough.TextLanguage.SPANISH
                ),
                "completed_on": "2026-07-23",
                "has_platinum": "",
                "platinum_earned_on": "",
                "is_platinum_target": "",
                "access_type": (
                    GameAccess.AccessType.OWNED
                ),
                "platform_name": (
                    GameAccess.Platform.PC
                ),
                "store": GameAccess.Store.XBOX,
                "notes": "",
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

        self.assertEqual(
            form.cleaned_data[
                "completed_text_language"
            ],
            Playthrough.TextLanguage.UNSPECIFIED,
        )

        self.assertIsNone(
            form.cleaned_data["completed_on"]
        )

    def test_backfill_creates_completed_playthrough(
        self,
    ):
        entry, access = self.create_completed_entry()

        output = StringIO()

        call_command(
            "backfill_completed_playthroughs",
            stdout=output,
        )

        playthrough = entry.playthroughs.get()

        self.assertEqual(
            playthrough.number,
            1,
        )
        self.assertEqual(
            playthrough.status,
            Playthrough.Status.COMPLETED,
        )
        self.assertEqual(
            playthrough.text_language,
            Playthrough.TextLanguage.UNSPECIFIED,
        )
        self.assertEqual(
            playthrough.access,
            access,
        )
        self.assertIsNone(
            playthrough.started_on
        )
        self.assertIsNone(
            playthrough.finished_on
        )

    def test_backfill_dry_run_does_not_create_records(
        self,
    ):
        entry, _access = self.create_completed_entry()

        output = StringIO()

        call_command(
            "backfill_completed_playthroughs",
            dry_run=True,
            stdout=output,
        )

        self.assertEqual(
            entry.playthroughs.count(),
            0,
        )
        self.assertIn(
            "[DRY RUN]",
            output.getvalue(),
        )

    def test_backfill_ignores_non_completed_entries(
        self,
    ):
        game = Game.objects.create(
            title="Plan to Play Game",
        )

        entry = LibraryEntry.objects.create(
            game=game,
            status=LibraryEntry.Status.PLAN_TO_PLAY,
        )

        call_command(
            "backfill_completed_playthroughs",
            stdout=StringIO(),
        )

        self.assertEqual(
            entry.playthroughs.count(),
            0,
        )

    def test_backfill_is_idempotent(self):
        entry, _access = self.create_completed_entry()

        call_command(
            "backfill_completed_playthroughs",
            stdout=StringIO(),
        )

        second_output = StringIO()

        call_command(
            "backfill_completed_playthroughs",
            stdout=second_output,
        )

        self.assertEqual(
            entry.playthroughs.count(),
            1,
        )

        self.assertIn(
            "No completed entries require backfill.",
            second_output.getvalue(),
        )


class GameKirokuCompetitiveRankTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="competitive-owner",
            password="test-password",
        )

        cls.game = Game.objects.create(
            title="Rocket League",
        )
        cls.entry = LibraryEntry.objects.create(
            game=cls.game,
            status=LibraryEntry.Status.MULTIPLAYER,
        )

        cls.mode = CompetitiveMode.objects.create(
            library_entry=cls.entry,
            name="2v2",
            display_order=20,
            is_active=True,
        )
        cls.tier = CompetitiveRankTier.objects.create(
            library_entry=cls.entry,
            name="Champion I",
            rank_order=160,
            uses_divisions=True,
            division_count=4,
        )

        cls.other_game = Game.objects.create(
            title="Battlefield REDSEC",
        )
        cls.other_entry = LibraryEntry.objects.create(
            game=cls.other_game,
            status=LibraryEntry.Status.MULTIPLAYER,
        )
        cls.other_mode = CompetitiveMode.objects.create(
            library_entry=cls.other_entry,
            name="Ranked Battle Royale",
            display_order=10,
            is_active=True,
        )
        cls.other_tier = CompetitiveRankTier.objects.create(
            library_entry=cls.other_entry,
            name="Gold",
            rank_order=40,
            uses_divisions=True,
            division_count=5,
        )

    def create_record(
        self,
        *,
        mode=None,
        tier=None,
        division=1,
        recorded_at=None,
        season="Season 23",
        notes="",
    ):
        return CompetitiveRankRecord.objects.create(
            mode=mode or self.mode,
            rank_tier=tier or self.tier,
            division=division,
            season=season,
            recorded_at=recorded_at or timezone.now(),
            notes=notes,
        )

    def create_mode_url(self):
        return reverse(
            "games:create_competitive_mode",
            kwargs={
                "slug": self.game.slug,
            },
        )

    def create_tier_url(self):
        return reverse(
            "games:create_competitive_tier",
            kwargs={
                "slug": self.game.slug,
            },
        )

    def create_record_url(self):
        return reverse(
            "games:create_competitive_record",
            kwargs={
                "slug": self.game.slug,
            },
        )

    def update_mode_url(self, mode=None):
        selected_mode = mode or self.mode

        return reverse(
            "games:update_competitive_mode",
            kwargs={
                "slug": self.game.slug,
                "mode_id": selected_mode.pk,
            },
        )

    def delete_mode_url(self, mode=None):
        selected_mode = mode or self.mode

        return reverse(
            "games:delete_competitive_mode",
            kwargs={
                "slug": self.game.slug,
                "mode_id": selected_mode.pk,
            },
        )

    def delete_tier_url(self, tier=None):
        selected_tier = tier or self.tier

        return reverse(
            "games:delete_competitive_tier",
            kwargs={
                "slug": self.game.slug,
                "tier_id": selected_tier.pk,
            },
        )

    def update_record_url(self, record):
        return reverse(
            "games:update_competitive_record",
            kwargs={
                "slug": self.game.slug,
                "record_id": record.pk,
            },
        )

    def delete_record_url(self, record):
        return reverse(
            "games:delete_competitive_record",
            kwargs={
                "slug": self.game.slug,
                "record_id": record.pk,
            },
        )

    def timestamp_value(self, value):
        return timezone.localtime(value).strftime(
            "%Y-%m-%dT%H:%M"
        )

    def test_competitive_ranking_is_public_but_controls_are_private(
        self,
    ):
        self.create_record(
            division=2,
        )

        response = self.client.get(
            self.game.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Competitive Ranking",
        )
        self.assertContains(
            response,
            "2v2",
        )
        self.assertContains(
            response,
            "Champion I",
        )
        self.assertContains(
            response,
            "<p>Division II</p>",
            html=True,
        )
        self.assertNotContains(
            response,
            "Competitive Setup",
        )

    def test_latest_record_is_current_rank(self):
        first_time = timezone.now()
        second_time = first_time + timedelta(
            minutes=5,
        )

        self.create_record(
            division=1,
            recorded_at=first_time,
        )
        latest_record = self.create_record(
            division=4,
            recorded_at=second_time,
        )

        self.assertEqual(
            self.mode.current_rank_record,
            latest_record,
        )

    def test_record_rejects_division_above_tier_limit(
        self,
    ):
        record = CompetitiveRankRecord(
            mode=self.mode,
            rank_tier=self.tier,
            division=5,
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_rank_without_divisions_rejects_division(
        self,
    ):
        unranked = CompetitiveRankTier.objects.create(
            library_entry=self.entry,
            name="Unranked",
            rank_order=0,
            uses_divisions=False,
            division_count=None,
        )

        record = CompetitiveRankRecord(
            mode=self.mode,
            rank_tier=unranked,
            division=1,
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_record_rejects_tier_from_another_game(
        self,
    ):
        record = CompetitiveRankRecord(
            mode=self.mode,
            rank_tier=self.other_tier,
            division=1,
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_anonymous_creation_redirects_to_login(
        self,
    ):
        response = self.client.post(
            self.create_mode_url(),
            {
                "new-competitive-mode-name": "1v1",
                "new-competitive-mode-display_order": "10",
                "new-competitive-mode-is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("login"),
            response.url,
        )
        self.assertFalse(
            CompetitiveMode.objects.filter(
                library_entry=self.entry,
                name="1v1",
            ).exists()
        )

    def test_authenticated_get_to_mutation_route_returns_405(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.create_record_url()
        )

        self.assertEqual(response.status_code, 405)

    def test_owner_can_create_competitive_mode(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_mode_url(),
            {
                "new-competitive-mode-name": "1v1",
                "new-competitive-mode-display_order": "10",
                "new-competitive-mode-is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        created_mode = CompetitiveMode.objects.get(
            library_entry=self.entry,
            name="1v1",
        )

        self.assertEqual(
            created_mode.display_order,
            10,
        )
        self.assertTrue(
            created_mode.is_active
        )

    def test_owner_can_create_competitive_tier(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_tier_url(),
            {
                "new-competitive-tier-name": (
                    "Diamond III"
                ),
                "new-competitive-tier-rank_order": (
                    "150"
                ),
                "new-competitive-tier-uses_divisions": (
                    "on"
                ),
                "new-competitive-tier-division_count": (
                    "4"
                ),
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        created_tier = (
            CompetitiveRankTier.objects.get(
                library_entry=self.entry,
                name="Diamond III",
            )
        )

        self.assertEqual(
            created_tier.rank_order,
            150,
        )
        self.assertEqual(
            created_tier.division_count,
            4,
        )

    def test_owner_can_create_rank_record(self):
        self.client.force_login(self.owner)

        recorded_at = timezone.now().replace(
            second=0,
            microsecond=0,
        )

        response = self.client.post(
            self.create_record_url(),
            {
                "new-competitive-record-mode": str(
                    self.mode.pk
                ),
                "new-competitive-record-rank_tier": str(
                    self.tier.pk
                ),
                "new-competitive-record-division": "3",
                "new-competitive-record-season": (
                    "Season 23"
                ),
                "new-competitive-record-recorded_at": (
                    self.timestamp_value(
                        recorded_at
                    )
                ),
                "new-competitive-record-notes": (
                    "Promotion match."
                ),
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        record = CompetitiveRankRecord.objects.get(
            mode=self.mode,
        )

        self.assertEqual(
            record.rank_tier,
            self.tier,
        )
        self.assertEqual(
            record.division,
            3,
        )
        self.assertEqual(
            record.season,
            "Season 23",
        )
        self.assertEqual(
            record.notes,
            "Promotion match.",
        )

    def test_owner_can_update_rank_record(self):
        record = self.create_record(
            division=1,
        )
        new_time = timezone.now().replace(
            second=0,
            microsecond=0,
        )

        self.client.force_login(self.owner)

        prefix = (
            f"competitive-record-{record.pk}"
        )

        response = self.client.post(
            self.update_record_url(record),
            {
                f"{prefix}-mode": str(
                    self.mode.pk
                ),
                f"{prefix}-rank_tier": str(
                    self.tier.pk
                ),
                f"{prefix}-division": "3",
                f"{prefix}-season": "Season 24",
                f"{prefix}-recorded_at": (
                    self.timestamp_value(
                        new_time
                    )
                ),
                f"{prefix}-notes": (
                    "Updated placement."
                ),
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        record.refresh_from_db()

        self.assertEqual(
            record.division,
            3,
        )
        self.assertEqual(
            record.season,
            "Season 24",
        )
        self.assertEqual(
            record.notes,
            "Updated placement.",
        )

    def test_deleting_latest_record_restores_previous_rank(
        self,
    ):
        first_time = timezone.now()
        second_time = first_time + timedelta(
            minutes=10,
        )

        previous_record = self.create_record(
            division=2,
            recorded_at=first_time,
        )
        latest_record = self.create_record(
            division=4,
            recorded_at=second_time,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_record_url(
                latest_record
            )
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )
        self.assertFalse(
            CompetitiveRankRecord.objects.filter(
                pk=latest_record.pk,
            ).exists()
        )
        self.assertEqual(
            self.mode.current_rank_record,
            previous_record,
        )

    def test_archived_mode_is_excluded_from_new_updates(
        self,
    ):
        self.client.force_login(self.owner)

        prefix = (
            f"competitive-mode-{self.mode.pk}"
        )

        response = self.client.post(
            self.update_mode_url(),
            {
                f"{prefix}-name": self.mode.name,
                f"{prefix}-display_order": "20",
            },
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )

        self.mode.refresh_from_db()

        self.assertFalse(
            self.mode.is_active
        )

        detail_response = self.client.get(
            self.game.get_absolute_url()
        )

        mode_queryset = (
            detail_response.context[
                "competitive_record_form"
            ]
            .fields["mode"]
            .queryset
        )

        self.assertNotIn(
            self.mode,
            mode_queryset,
        )

    def test_mode_with_history_cannot_be_deleted(
        self,
    ):
        self.create_record()
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_mode_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            (
                "This mode has rank history and "
                "cannot be deleted."
            ),
        )
        self.assertTrue(
            CompetitiveMode.objects.filter(
                pk=self.mode.pk,
            ).exists()
        )

    def test_empty_mode_can_be_deleted(self):
        empty_mode = CompetitiveMode.objects.create(
            library_entry=self.entry,
            name="Test Mode",
            display_order=99,
            is_active=True,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_mode_url(
                mode=empty_mode,
            )
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )
        self.assertFalse(
            CompetitiveMode.objects.filter(
                pk=empty_mode.pk,
            ).exists()
        )

    def test_tier_with_history_cannot_be_deleted(
        self,
    ):
        self.create_record()
        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_tier_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            (
                "This rank is used by the history "
                "and cannot be deleted."
            ),
        )
        self.assertTrue(
            CompetitiveRankTier.objects.filter(
                pk=self.tier.pk,
            ).exists()
        )

    def test_empty_tier_can_be_deleted(self):
        empty_tier = (
            CompetitiveRankTier.objects.create(
                library_entry=self.entry,
                name="Temporary Rank",
                rank_order=999,
                uses_divisions=False,
                division_count=None,
            )
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            self.delete_tier_url(
                tier=empty_tier,
            )
        )

        self.assertRedirects(
            response,
            self.game.get_absolute_url(),
        )
        self.assertFalse(
            CompetitiveRankTier.objects.filter(
                pk=empty_tier.pk,
            ).exists()
        )

    def test_foreign_record_cannot_be_updated_through_game(
        self,
    ):
        foreign_record = self.create_record(
            mode=self.other_mode,
            tier=self.other_tier,
            division=2,
        )

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_competitive_record",
                kwargs={
                    "slug": self.game.slug,
                    "record_id": foreign_record.pk,
                },
            ),
            {},
        )

        self.assertEqual(
            response.status_code,
            404,
        )
        self.assertTrue(
            CompetitiveRankRecord.objects.filter(
                pk=foreign_record.pk,
            ).exists()
        )

    def test_only_selected_tier_builds_owner_form(
        self,
    ):
        second_tier = (
            CompetitiveRankTier.objects.create(
                library_entry=self.entry,
                name="Diamond III",
                rank_order=150,
                uses_divisions=True,
                division_count=4,
            )
        )

        self.client.force_login(self.owner)

        regular_response = self.client.get(
            self.game.get_absolute_url()
        )

        regular_tiers = (
            regular_response.context[
                "competitive_rank_tiers"
            ]
        )

        self.assertTrue(
            all(
                tier.owner_form is None
                for tier in regular_tiers
            )
        )

        managed_response = self.client.get(
            self.game.get_absolute_url(),
            {
                "manage_tier": self.tier.pk,
            },
        )

        managed_tiers = (
            managed_response.context[
                "competitive_rank_tiers"
            ]
        )

        selected_tier = next(
            tier
            for tier in managed_tiers
            if tier.pk == self.tier.pk
        )
        unselected_tier = next(
            tier
            for tier in managed_tiers
            if tier.pk == second_tier.pk
        )

        self.assertTrue(
            selected_tier.is_managed
        )
        self.assertIsNotNone(
            selected_tier.owner_form
        )
        self.assertFalse(
            unselected_tier.is_managed
        )
        self.assertIsNone(
            unselected_tier.owner_form
        )


class GameKirokuCompetitivePresetCommandTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.rocket_league = Game.objects.create(
            title="Rocket League",
        )
        cls.rocket_entry = (
            LibraryEntry.objects.create(
                game=cls.rocket_league,
                status=(
                    LibraryEntry.Status.MULTIPLAYER
                ),
            )
        )

        cls.battlefield = Game.objects.create(
            title="Battlefield 6",
        )
        cls.battlefield_entry = (
            LibraryEntry.objects.create(
                game=cls.battlefield,
                status=(
                    LibraryEntry.Status.MULTIPLAYER
                ),
            )
        )

    def run_preset(
        self,
        *,
        game,
        preset,
        dry_run=False,
    ):
        output = StringIO()

        call_command(
            "setup_competitive_presets",
            game=game,
            preset=preset,
            dry_run=dry_run,
            stdout=output,
        )

        return output.getvalue()

    def test_dry_run_does_not_write_changes(
        self,
    ):
        output = self.run_preset(
            game="Rocket League",
            preset="rocket-league",
            dry_run=True,
        )

        self.assertIn(
            "Dry run",
            output,
        )
        self.assertFalse(
            CompetitiveMode.objects.filter(
                library_entry=self.rocket_entry,
            ).exists()
        )
        self.assertFalse(
            CompetitiveRankTier.objects.filter(
                library_entry=self.rocket_entry,
            ).exists()
        )

    def test_rocket_league_preset_is_idempotent(
        self,
    ):
        self.run_preset(
            game="Rocket League",
            preset="rocket-league",
        )
        self.run_preset(
            game="Rocket League",
            preset="rocket-league",
        )

        modes = CompetitiveMode.objects.filter(
            library_entry=self.rocket_entry,
        )
        tiers = (
            CompetitiveRankTier.objects.filter(
                library_entry=self.rocket_entry,
            )
        )

        self.assertEqual(
            modes.count(),
            3,
        )
        self.assertEqual(
            tiers.count(),
            23,
        )
        self.assertSetEqual(
            set(
                modes.values_list(
                    "name",
                    flat=True,
                )
            ),
            {
                "1V1",
                "2V2",
                "3V3",
            },
        )
        self.assertTrue(
            tiers.filter(
                name="Supersonic Legend",
            ).exists()
        )

    def test_preset_normalizes_existing_tier_without_losing_history(
        self,
    ):
        mode = CompetitiveMode.objects.create(
            library_entry=self.rocket_entry,
            name="2V2",
            display_order=20,
            is_active=True,
        )
        tier = (
            CompetitiveRankTier.objects.create(
                library_entry=self.rocket_entry,
                name="Champion I",
                rank_order=140,
                uses_divisions=True,
                division_count=4,
            )
        )
        record = (
            CompetitiveRankRecord.objects.create(
                mode=mode,
                rank_tier=tier,
                division=2,
                season="Season 23",
                recorded_at=timezone.now(),
            )
        )

        original_tier_id = tier.pk

        self.run_preset(
            game="Rocket League",
            preset="rocket-league",
        )

        tier.refresh_from_db()
        record.refresh_from_db()

        self.assertEqual(
            tier.pk,
            original_tier_id,
        )
        self.assertEqual(
            tier.rank_order,
            160,
        )
        self.assertEqual(
            record.rank_tier_id,
            original_tier_id,
        )
        self.assertEqual(
            record.division,
            2,
        )

    def test_redsec_preset_is_added_to_battlefield_6(
        self,
    ):
        self.run_preset(
            game="Battlefield 6",
            preset="redsec",
        )

        self.assertTrue(
            CompetitiveMode.objects.filter(
                library_entry=(
                    self.battlefield_entry
                ),
                name="Ranked Battle Royale",
            ).exists()
        )
        self.assertEqual(
            CompetitiveRankTier.objects.filter(
                library_entry=(
                    self.battlefield_entry
                ),
            ).count(),
            9,
        )
        self.assertTrue(
            CompetitiveRankTier.objects.filter(
                library_entry=(
                    self.battlefield_entry
                ),
                name="Bronze",
                division_count=5,
            ).exists()
        )
        self.assertFalse(
            Game.objects.filter(
                title="Battlefield REDSEC",
            ).exists()
        )

    def test_missing_game_returns_command_error(
        self,
    ):
        with self.assertRaises(CommandError):
            self.run_preset(
                game="Missing Game",
                preset="rocket-league",
            )


