from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction
from django.db.models import Q

from games.models import (
    CompetitiveMode,
    CompetitiveRankTier,
    LibraryEntry,
)


def build_rocket_league_tiers():
    tiers = [
        {
            "name": "Unranked",
            "rank_order": 0,
            "uses_divisions": False,
            "division_count": None,
        },
    ]

    rank_order = 10

    for rank_group in (
        "Bronze",
        "Silver",
        "Gold",
        "Platinum",
        "Diamond",
        "Champion",
        "Grand Champion",
    ):
        for level in (
            "I",
            "II",
            "III",
        ):
            tiers.append(
                {
                    "name": f"{rank_group} {level}",
                    "rank_order": rank_order,
                    "uses_divisions": True,
                    "division_count": 4,
                }
            )

            rank_order += 10

    tiers.append(
        {
            "name": "Supersonic Legend",
            "rank_order": rank_order,
            "uses_divisions": True,
            "division_count": 4,
        }
    )

    return tuple(tiers)


ROCKET_LEAGUE_PRESET = {
    "label": "Rocket League",
    "modes": (
        {
            "name": "1V1",
            "display_order": 10,
            "is_active": True,
        },
        {
            "name": "2V2",
            "display_order": 20,
            "is_active": True,
        },
        {
            "name": "3V3",
            "display_order": 30,
            "is_active": True,
        },
    ),
    "tiers": build_rocket_league_tiers(),
}


REDSEC_PRESET = {
    "label": "Battlefield REDSEC",
    "modes": (
        {
            "name": "Ranked Battle Royale",
            "display_order": 10,
            "is_active": True,
        },
    ),
    "tiers": (
        {
            "name": "Unranked",
            "rank_order": 0,
            "uses_divisions": False,
            "division_count": None,
        },
        {
            "name": "Rookie",
            "rank_order": 10,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Bronze",
            "rank_order": 20,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Silver",
            "rank_order": 30,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Gold",
            "rank_order": 40,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Platinum",
            "rank_order": 50,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Diamond",
            "rank_order": 60,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Master",
            "rank_order": 70,
            "uses_divisions": True,
            "division_count": 5,
        },
        {
            "name": "Elite Top 250",
            "rank_order": 80,
            "uses_divisions": False,
            "division_count": None,
        },
    ),
}


PRESETS = {
    "rocket-league": ROCKET_LEAGUE_PRESET,
    "redsec": REDSEC_PRESET,
}


class Command(BaseCommand):
    help = (
        "Create missing competitive modes and rank tiers "
        "for a Game Kiroku library entry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--game",
            required=True,
            help=(
                "Exact game title or local game slug."
            ),
        )

        parser.add_argument(
            "--preset",
            required=True,
            choices=tuple(PRESETS),
            help="Competitive configuration preset.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show the changes without writing "
                "to the database."
            ),
        )

    def handle(self, *args, **options):
        game_lookup = str(
            options["game"]
        ).strip()

        preset_key = options["preset"]
        preset = PRESETS[preset_key]
        dry_run = options["dry_run"]

        entries = (
            LibraryEntry.objects
            .select_related("game")
            .filter(
                Q(
                    game__title__iexact=game_lookup
                )
                | Q(
                    game__slug=game_lookup
                )
            )
            .distinct()
        )

        entry_count = entries.count()

        if entry_count == 0:
            raise CommandError(
                (
                    "No library entry was found for "
                    f"'{game_lookup}'."
                )
            )

        if entry_count > 1:
            matches = ", ".join(
                entry.game.slug
                for entry in entries
            )

            raise CommandError(
                (
                    "More than one library entry matched. "
                    "Run the command using one of these "
                    f"slugs: {matches}"
                )
            )

        entry = entries.get()

        self.stdout.write(
            (
                f"Game: {entry.game.title}\n"
                f"Preset: {preset['label']}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run: no database changes "
                    "will be written."
                )
            )

        created_modes = 0
        existing_modes = 0
        created_tiers = 0
        existing_tiers = 0

        with transaction.atomic():
            for mode_data in preset["modes"]:
                existing_mode = (
                    CompetitiveMode.objects
                    .filter(
                        library_entry=entry,
                        name__iexact=(
                            mode_data["name"]
                        ),
                    )
                    .first()
                )

                if existing_mode is not None:
                    existing_modes += 1

                    self.stdout.write(
                        (
                            "[EXISTS] Mode: "
                            f"{existing_mode.name}"
                        )
                    )

                    self._report_mode_differences(
                        existing_mode,
                        mode_data,
                    )

                    continue

                if dry_run:
                    created_modes += 1

                    self.stdout.write(
                        (
                            "[WOULD CREATE] Mode: "
                            f"{mode_data['name']}"
                        )
                    )

                    continue

                CompetitiveMode.objects.create(
                    library_entry=entry,
                    **mode_data,
                )

                created_modes += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        (
                            "Created mode: "
                            f"{mode_data['name']}"
                        )
                    )
                )

            preset_tier_names = {
                tier_data["name"].casefold()
                for tier_data in preset["tiers"]
            }

            existing_tier_list = list(
                CompetitiveRankTier.objects
                .filter(
                    library_entry=entry,
                )
                .order_by(
                    "rank_order",
                    "name",
                )
            )

            existing_tiers_by_name = {
                tier.name.casefold(): tier
                for tier in existing_tier_list
            }

            custom_tiers = [
                tier
                for tier in existing_tier_list
                if (
                    tier.name.casefold()
                    not in preset_tier_names
                )
            ]

            if dry_run:
                for tier_data in preset["tiers"]:
                    existing_tier = (
                        existing_tiers_by_name.get(
                            tier_data[
                                "name"
                            ].casefold()
                        )
                    )

                    if existing_tier is None:
                        created_tiers += 1

                        self.stdout.write(
                            (
                                "[WOULD CREATE] Rank: "
                                f"{tier_data['name']}"
                            )
                        )

                        continue

                    existing_tiers += 1

                    differences = (
                        self._tier_differences(
                            existing_tier,
                            tier_data,
                        )
                    )

                    if differences:
                        self.stdout.write(
                            (
                                "[WOULD UPDATE] Rank: "
                                f"{existing_tier.name}"
                            )
                        )

                        self.stdout.write(
                            self.style.WARNING(
                                (
                                    "  "
                                    + "; ".join(
                                        differences
                                    )
                                )
                            )
                        )
                    else:
                        self.stdout.write(
                            (
                                "[EXISTS] Rank: "
                                f"{existing_tier.name}"
                            )
                        )

                next_custom_order = (
                    max(
                        tier_data["rank_order"]
                        for tier_data
                        in preset["tiers"]
                    )
                    + 10
                )

                for custom_tier in custom_tiers:
                    if (
                        custom_tier.rank_order
                        != next_custom_order
                    ):
                        self.stdout.write(
                            (
                                "[WOULD MOVE] Custom rank: "
                                f"{custom_tier.name} "
                                f"{custom_tier.rank_order} "
                                f"→ {next_custom_order}"
                            )
                        )

                    next_custom_order += 10

            else:
                temporary_base = 30000

                if (
                    temporary_base
                    + len(existing_tier_list)
                    >= 32767
                ):
                    raise CommandError(
                        (
                            "There are too many rank tiers "
                            "to normalize safely."
                        )
                    )

                # First move every existing tier to a
                # temporary unique order. This avoids
                # transient unique-constraint conflicts.
                for index, tier in enumerate(
                    existing_tier_list
                ):
                    tier.rank_order = (
                        temporary_base + index
                    )

                    tier.save(
                        update_fields=[
                            "rank_order",
                            "updated_at",
                        ]
                    )

                for tier_data in preset["tiers"]:
                    existing_tier = (
                        existing_tiers_by_name.get(
                            tier_data[
                                "name"
                            ].casefold()
                        )
                    )

                    if existing_tier is None:
                        CompetitiveRankTier.objects.create(
                            library_entry=entry,
                            **tier_data,
                        )

                        created_tiers += 1

                        self.stdout.write(
                            self.style.SUCCESS(
                                (
                                    "Created rank: "
                                    f"{tier_data['name']}"
                                )
                            )
                        )

                        continue

                    existing_tiers += 1

                    existing_tier.name = (
                        tier_data["name"]
                    )
                    existing_tier.rank_order = (
                        tier_data["rank_order"]
                    )
                    existing_tier.uses_divisions = (
                        tier_data[
                            "uses_divisions"
                        ]
                    )
                    existing_tier.division_count = (
                        tier_data[
                            "division_count"
                        ]
                    )

                    existing_tier.save(
                        update_fields=[
                            "name",
                            "rank_order",
                            "uses_divisions",
                            "division_count",
                            "updated_at",
                        ]
                    )

                    self.stdout.write(
                        (
                            "[SYNCED] Rank: "
                            f"{existing_tier.name}"
                        )
                    )

                next_custom_order = (
                    max(
                        tier_data["rank_order"]
                        for tier_data
                        in preset["tiers"]
                    )
                    + 10
                )

                for custom_tier in custom_tiers:
                    custom_tier.rank_order = (
                        next_custom_order
                    )

                    custom_tier.save(
                        update_fields=[
                            "rank_order",
                            "updated_at",
                        ]
                    )

                    self.stdout.write(
                        (
                            "[MOVED] Custom rank: "
                            f"{custom_tier.name} "
                            f"→ {next_custom_order}"
                        )
                    )

                    next_custom_order += 10

            if dry_run:
                transaction.set_rollback(True)

        action = (
            "would be created"
            if dry_run
            else "created"
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Preset complete.\n"
                    f"Modes {action}: "
                    f"{created_modes}\n"
                    f"Existing modes preserved: "
                    f"{existing_modes}\n"
                    f"Ranks {action}: "
                    f"{created_tiers}\n"
                    f"Existing ranks preserved: "
                    f"{existing_tiers}"
                )
            )
        )

    def _report_mode_differences(
        self,
        existing_mode,
        expected,
    ):
        differences = []

        if (
            existing_mode.display_order
            != expected["display_order"]
        ):
            differences.append(
                (
                    "display order "
                    f"{existing_mode.display_order} "
                    f"(preset: "
                    f"{expected['display_order']})"
                )
            )

        if (
            existing_mode.is_active
            != expected["is_active"]
        ):
            differences.append(
                (
                    "active state "
                    f"{existing_mode.is_active} "
                    f"(preset: "
                    f"{expected['is_active']})"
                )
            )

        if differences:
            self.stdout.write(
                self.style.WARNING(
                    (
                        "  Existing values preserved: "
                        + "; ".join(differences)
                    )
                )
            )

    def _tier_differences(
        self,
        existing_tier,
        expected,
    ):
        differences = []

        fields = (
            "rank_order",
            "uses_divisions",
            "division_count",
        )

        for field_name in fields:
            current_value = getattr(
                existing_tier,
                field_name,
            )
            expected_value = expected[
                field_name
            ]

            if current_value != expected_value:
                differences.append(
                    (
                        f"{field_name}: "
                        f"{current_value} "
                        f"→ {expected_value}"
                    )
                )

        return differences


