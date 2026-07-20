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
            status=LibraryEntry.Status.PLAYING,
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

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "games:update_entry",
                kwargs={
                    "slug": multiplayer_game.slug,
                },
            ),
            {
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

