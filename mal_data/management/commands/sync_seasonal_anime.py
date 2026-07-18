from django.core.management.base import BaseCommand

from mal_data.services.seasonal_sync import sync_seasonal_anime


class Command(BaseCommand):
    help = "Sync seasonal anime from AniList."

    def add_arguments(self, parser):
        parser.add_argument("season", type=str, help="WINTER, SPRING, SUMMER or FALL")
        parser.add_argument("season_year", type=int)

    def handle(self, *args, **options):
        season = options["season"]
        season_year = options["season_year"]

        result = sync_seasonal_anime(season, season_year)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seasonal sync completed: {result['season']} {result['season_year']} "
                f"· Created: {result['created_count']} "
                f"· Updated: {result['updated_count']} "
                f"· Total: {result['total_count']}"
            )
        )