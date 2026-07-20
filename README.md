# MVS Tracker

MVS Tracker is a modular personal media platform built to organize what I want to consume, record what I actually do, and analyze my progress across anime, manga, and video games.

The project began as MAL Insight Lab, a personal MyAnimeList analytics dashboard. It is now being transformed into a broader Django platform composed of independent but connected modules.

## Current Status

MVS Tracker is in active development.

The application currently runs locally and uses Supabase PostgreSQL as its shared database.

The platform supports two access levels:

- Public read-only access for browsing data.
- Authenticated owner access for synchronization, editing, tracking actions, and administration.

Public registration is intentionally disabled.

## Modules

### MAL Insights

Status: **Available**

MAL Insights is the anime and manga analytics module connected to MyAnimeList and enriched with AniList metadata.

Current features include:

- Anime library by MAL list status.
- Watching and rewatching support.
- Episode Signals.
- Seasonal anime discovery.
- Yearly seasonal `ALL` mode.
- Provisional TBA anime bucket.
- Franchise relation scanning.
- Franchise Audit.
- Sequel Radar.
- Broadcast watchlist.
- Plan to Watch actions.
- Search and manual rescue tools.
- AniList metadata enrichment.
- Manual synchronization controls.
- Public read-only mode.
- Owner-only write actions.

MAL Insights is available at:

```text
/anime/
```

### Game Kiroku / ゲーム記録

Status: **Planned**

Game Kiroku will manage the personal video game library and backlog.

Planned MVP features include:

- Library and wishlist.
- Playing, paused, dropped, completed, Plan to Play, and multiplayer states.
- Platforms and storefronts.
- Manual franchise grouping.
- Playthrough history.
- Language used for each playthrough.
- Optional manual progress.
- IGDB main-story duration estimates.
- Platinum indicator.
- Library and completion analytics.

The planned route is:

```text
/games/
```

### Hibi Log / 日々ログ

Status: **Planned**

Hibi Log will record real daily activity across games, anime, and manga.

Planned features include:

- Daily sessions.
- Calendar view.
- Time spent.
- Episodes, chapters, and game progress.
- Progress ranges.
- Notes and session impressions.
- Weekly summaries.
- Activity analytics.
- Comparison between plans and actual activity.

The planned route is:

```text
/activity/
```

## Platform Routes

```text
/                    MVS Tracker module selector
/accounts/login/     Owner login
/accounts/logout/    Owner logout
/anime/              MAL Insights
/games/              Game Kiroku — planned
/activity/           Hibi Log — planned
/admin/              Django administration
/dashboard/          Future global platform dashboard
```

## Access Model

Read-only views are publicly accessible.

Actions that modify MyAnimeList, Supabase, or local application data require:

- An authenticated user.
- A POST request.
- CSRF validation.

Protected actions currently include:

- MAL library synchronization.
- Relation synchronization.
- Seasonal board synchronization.
- Add to Plan to Watch.
- Manual anime rescue.

Opening a normal page never triggers an automatic synchronization.

## Tech Stack

- Python
- Django
- PostgreSQL
- Supabase PostgreSQL
- MyAnimeList API v2
- AniList GraphQL API
- HTML
- CSS
- Django Authentication
- python-dotenv
- requests
- dj-database-url

## Project Structure

```text
mvs-tracker/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── core/
│   ├── static/core/
│   ├── templates/core/
│   ├── apps.py
│   ├── urls.py
│   └── views.py
│
├── mal_data/
│   ├── management/commands/
│   ├── migrations/
│   ├── services/
│   ├── static/mal_data/
│   ├── web/
│   │   ├── dashboard.py
│   │   ├── library.py
│   │   ├── relations.py
│   │   ├── search.py
│   │   ├── seasonal.py
│   │   └── sync.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── urls.py
│
├── templates/
│   ├── registration/
│   ├── mal_data/
│   └── base.html
│
├── manage.py
├── requirements.txt
└── README.md
```

The technical Django app name `mal_data` is intentionally preserved to avoid unnecessary migration and database table changes. Its public module name is **MAL Insights**.

## Environment Variables

Create a `.env` file in the project root.

### Supabase PostgreSQL

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

DATABASE_URL=postgresql://...

MAL_ACCESS_TOKEN=your-mal-access-token

ALLOWED_HOSTS=127.0.0.1,localhost
```

When `DATABASE_URL` is present, Django uses it as the primary PostgreSQL connection.

### Local PostgreSQL

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

DB_NAME=mvs_tracker
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_HOST=localhost
DB_PORT=5432

MAL_ACCESS_TOKEN=your-mal-access-token

ALLOWED_HOSTS=127.0.0.1,localhost
```

## Local Setup

Create and activate the virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply migrations:

```bash
python manage.py migrate
```

Create an owner account when necessary:

```bash
python manage.py createsuperuser
```

Run the development server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## MAL Insights Commands

### Synchronize a MAL status

```bash
python manage.py fetch_anime_status watching
python manage.py fetch_anime_status completed
python manage.py fetch_anime_status on_hold
python manage.py fetch_anime_status dropped
python manage.py fetch_anime_status plan_to_watch
```

### Synchronize AniList airing data

```bash
python manage.py sync_airing_data --dashboard
```

### Inspect airing data

```bash
python manage.py inspect_airing_data 63832
```

### Synchronize anime relations

```bash
python manage.py fetch_anime_relations 32182
```

### Rescue a manually tracked anime

```bash
python manage.py rescue_anime_entry 46488 \
  --status watching \
  --episodes-watched 1 \
  --sync-airing
```

### Synchronize a seasonal board

```bash
python manage.py sync_seasonal_anime SUMMER 2026
```

## Data Sources

### MyAnimeList

MyAnimeList is the primary source for personal anime and manga list data.

It is used for:

- Personal list status.
- Progress.
- Scores.
- Rewatch state.
- Official Plan to Watch actions.
- Anime and manga relations.

### AniList

AniList is used as a public metadata and discovery source.

It provides:

- Airing information.
- Next episode data.
- Estimated aired episodes.
- Native titles.
- Streaming links.
- Seasonal anime.
- Search results.
- Upcoming TBA entries.

AniList is not used as the source of the personal library.

### IGDB

IGDB is planned as the primary metadata source for Game Kiroku.

Imported game metadata will be stored locally instead of being requested every time a page loads.

## Development Principles

- One Django project containing multiple connected modules.
- Shared authentication and database.
- Public reading, private writing.
- Local-first storage for imported metadata.
- Explicit synchronization instead of hidden writes during page loads.
- Semantic HTML when appropriate.
- Services separated from HTTP views.
- Modules organized by domain rather than one large view file.
- External APIs treated as import and synchronization sources, not permanent runtime dependencies.

## Roadmap

### Platform Foundation

- [x] Create the MVS Tracker module selector.
- [x] Move MAL Insights under `/anime/`.
- [x] Add shared authentication.
- [x] Add public read-only mode.
- [x] Protect write actions with login and POST.
- [x] Remove synchronization side effects from GET requests.
- [x] Modularize MAL Insights views.
- [ ] Add automated access and route tests.
- [ ] Add a future global dashboard.

### Game Kiroku

- [ ] Create the Django app.
- [ ] Define library and playthrough models.
- [ ] Integrate IGDB metadata imports.
- [ ] Build the game library.
- [ ] Add wishlist and filters.
- [ ] Add platinum tracking.
- [ ] Add game analytics.

### Hibi Log

- [ ] Define the shared activity-session model.
- [ ] Connect sessions to anime, manga, and games.
- [ ] Build the daily calendar.
- [ ] Add weekly summaries.
- [ ] Add activity analytics.

### MAL Insights

- [ ] Expand manga support.
- [ ] Add manga archive views.
- [ ] Explore chapter availability signals.
- [ ] Improve token renewal workflow.
- [ ] Improve entries without confirmed MAL IDs.

## Security

Never commit:

- `.env`
- Database credentials
- MAL access tokens
- API tokens
- Raw private API responses
- Local virtual environments
- Local database files
- Collected static output

## License

No license has been selected yet.
