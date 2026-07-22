from decimal import Decimal
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

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

