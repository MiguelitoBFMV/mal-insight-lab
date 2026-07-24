# MVS Tracker

MVS Tracker is a modular personal media platform built to organize what I want to consume, record what I actually do, and analyze my progress across anime, manga, video games, series, movies, and music.

The platform is organized around four content-tracking modules and one cross-module activity layer:

```text
MVS Tracker
├── MAL Insights
│   └── Anime & Manga
├── Game Kiroku
│   └── Video Games
├── Watchroom
│   └── Series & Movies
├── Music
│   └── Last.fm listening data
└── Hibi Log
    └── Daily activity across all four trackers
```

The project began as MAL Insight Lab, a personal MyAnimeList analytics dashboard. It is now a broader Django platform composed of independent but connected modules.

## Current Status

MVS Tracker is in active development.

The application currently runs locally and uses Supabase PostgreSQL as its shared database. MAL Insights and Game Kiroku are available.

The anime side of MAL Insights is functionally stable and includes automatic MyAnimeList OAuth renewal, optimized synchronization workflows, manual rescue support for entries omitted by the MAL list API, and unified Episode Signals for normal and manually rescued entries.

Game Kiroku has completed its MVP. The module now combines a local-first IGDB workflow, replay-aware playthrough history, additional-content tracking, a dedicated Platinum Collection, franchise timelines, completed-import history, and configurable competitive-rank tracking.

The platform supports two access levels:

- Public read-only access for browsing data.
- Authenticated owner access for synchronization, editing, tracking actions, OAuth connection, and administration.

Public registration is intentionally disabled.

## Modules

### MAL Insights

Status: **Available — anime workflow functionally complete**

MAL Insights is the anime and manga analytics module connected to MyAnimeList and enriched with AniList metadata.

Current anime features include:

- Anime library by MAL list status.
- Watching and rewatching support.
- Unified Episode Signals for Watching, Rewatching, and active manual rescues.
- Progress, score, and status refresh for active Episode Signal entries.
- AniList airing data, next-episode information, pending-episode calculations, and streaming links.
- Seasonal anime discovery.
- Add to Plan behavior that checks the real MAL list status before modifying an entry.
- Franchise relation scanning.
- Franchise Audit.
- Sequel Radar.
- Broadcast Watchlist.
- Search and manual rescue tools.
- Persistent `ManualTrackedAnime` fallbacks for entries omitted by the MAL list API.
- Command Logs for episode, score, and status changes.
- AniList metadata enrichment.
- Separate synchronization actions for MAL Library, Episode Signals, and Manual Rescues.
- Optimized MAL Library synchronization with Created, Updated, and Unchanged classification.
- Automatic MyAnimeList OAuth token renewal.
- A single forced token refresh and retry after a MAL `401 invalid_token` response.
- Public read-only mode.
- Owner-only synchronization and write actions.
- Automated regression tests for OAuth, MAL sync, Episode Signals, manual rescues, routes, and permissions.

The current synchronization controls are intentionally separated:

- **Sync MAL Library** updates the five MAL list statuses, personal progress, scores, Command Logs, Broadcast Watchlist data, and the local status context used by Sequel Radar.
- **Sync Signals** checks only locally active Watching and Rewatching entries, including active manual rescues, then updates personal MAL progress and AniList airing information.
- **Sync Manual Rescues** rebuilds and refreshes entries that the normal MAL list endpoint omits.
- **Connect / Renew MAL** starts the owner-only OAuth authorization flow when the account must be connected again.

Route:

```text
/anime/
```

### Game Kiroku / ゲーム記録

Status: **Available — MVP complete**

Game Kiroku is the video game library, playthrough, access, platinum, franchise, additional-content, and competitive-rank tracking module.

Current features include:

- Local game library stored in Supabase PostgreSQL.
- Dynamic dashboard with Owned, Wishlist, Completed, Platinum, Plan to Play, and Multiplayer metrics.
- Replay-aware completion analytics.
- Completion analytics that exclude persistent multiplayer games.
- Public library with search and filters for status, access type, platform, Platinum Unlocked, and Platinum Target.
- Platinum-filtered ordering by acquisition date, with unknown dates placed last.
- Rich individual game detail pages.
- Playing, Paused, Dropped, Completed, Plan to Play, and Multiplayer states.
- Manual status control for games without playthrough history.
- Playthrough-driven status synchronization when playthrough history exists.
- Multiple playthroughs per game.
- Automatic creation of `Playthrough 1` when a newly imported game starts as Completed.
- Historical backfill support for completed entries that predate automatic playthrough creation.
- Text language, platform access, progress, dates, notes, and hours per playthrough.
- `Unspecified` as a valid historical language fallback when the original language is unknown.
- Owned and Wishlist access records by platform and storefront, including Xbox / Game Pass as a store option.
- Owner controls for creating, editing, and deleting eligible access records.
- Historical protection for accesses already referenced by playthroughs.
- Main-story duration from IGDB with manual override support.
- Platinum tracking at `LibraryEntry` level, independent of the current platform.
- Optional platinum acquisition dates.
- Platinum targets for future goals.
- Dedicated Platinum Collection with the latest platinum, yearly history, unknown-date records, and future targets.
- Manual franchise grouping.
- Public franchise list and franchise detail pages.
- Franchise metrics for total, owned, active, Plan to Play, completed, and platinum games.
- Release timelines that can be ordered oldest-first or newest-first.
- Optional franchise logos.
- Dynamic franchise artwork selected from the most relevant library game.
- Representative-game priority of Playing, Completed, Paused, Multiplayer, Plan to Play, and Dropped.
- Owner controls for creating, editing, and safely deleting empty franchises.
- Assignment, movement, and removal of games from franchises without using Django admin.
- Optional franchise assignment during IGDB import.
- Owner-only forms for library entries, franchises, accesses, playthroughs, and additional content.
- Explicit IGDB search, review, import, linking, and refresh actions.
- Local-first storage of imported IGDB metadata.
- Exact-title-first IGDB search ranking with bundles and secondary editions deprioritized.
- Imported cover art, background artwork, synopsis, release date, genres, platforms, raw payload, and synchronization timestamp.
- Linking IGDB metadata to existing local games without replacing their slug, accesses, playthroughs, notes, or status.
- Creating a new `Game`, `LibraryEntry`, and initial `GameAccess` in one transactional import.
- Validation that prevents a platinum-marked entry from existing without at least one Owned access.
- Additional Content records for DLC, expansions, standalone expansions, and manually registered related content.
- IGDB detection of `dlcs`, `expansions`, `standalone_expansions`, and `parent_game` relationships.
- Choice to track detected content under its parent game or review it as a separate library game.
- Status, optional completion date, notes, synopsis, cover, release date, and raw IGDB payload for tracked additional content.
- Configurable competitive modes per game, such as Rocket League `1V1`, `2V2`, and `3V3`.
- Game-specific rank tiers with optional division systems.
- Timestamped competitive-rank history with season, rank, division, notes, and multiple updates on the same day.
- Current rank derived from the latest historical record instead of a separately overwritten field.
- Roman-numeral division display and per-tier maximum-division validation.
- Safe editing and deletion of rank records, with automatic fallback to the previous current rank.
- Mode archiving that preserves history while removing archived modes from new-record forms.
- Protected deletion of modes and tiers already referenced by rank history.
- Idempotent competitive presets for Rocket League and REDSEC inside Battlefield 6.
- Lazy tier management that renders only the selected tier editor on large configurations.
- Public read-only mode and owner-only write actions.
- Automated model, route, permission, dashboard, library, detail, platinum, franchise, playthrough, access, completed-import, competitive-ranking, preset-command, and form tests.

IGDB is treated as an import and enrichment source. Normal Game Kiroku pages read from Supabase and do not contact IGDB automatically. Search, import, linking, and refresh operations happen only after an explicit owner action.

Routes:

```text
/games/                               Dashboard
/games/library/                       Library
/games/library/<slug>/                Game detail
/games/platinum/                      Platinum Collection
/games/franchises/                    Franchise list
/games/franchises/<slug>/             Franchise detail
/games/igdb/search/                   Owner IGDB search
/games/igdb/<igdb_id>/import/         Owner import review
```

### Watchroom

Status: **Planned**

Descriptor: **Series & Movies**

Watchroom will manage media outside the anime ecosystem, including:

- Live-action series.
- Movies.
- Western cartoons.
- Animated films.
- Documentaries.
- Franchises and connected works.
- Personal status and progress.
- Rewatches.
- Library and backlog analytics.

Planned route:

```text
/watchroom/
```

### Music

Status: **Planned — final module**

The music module will use Last.fm as its primary listening-data source.

Planned features include:

- Artists, albums, and tracks.
- Scrobble history.
- Listening totals by period.
- Rankings and trends.
- Personal listening analytics.
- Yearly and monthly summaries.
- Data that can later feed Hibi Log.

Its final public name has not been selected yet.

Planned route:

```text
/music/
```

### Hibi Log / 日々ログ

Status: **Planned**

Hibi Log is the cross-module activity layer and the natural general dashboard of MVS Tracker.

The four tracking modules describe what content exists and the user's relationship with it. Hibi Log records what was actually done each day.

It will eventually connect activity from:

- MAL Insights.
- Game Kiroku.
- Watchroom.
- Music.

Planned features include:

- Daily sessions.
- Calendar view.
- Time spent.
- Episodes, chapters, and game progress.
- Series and movie activity.
- Music activity summaries.
- Progress ranges.
- Notes and session impressions.
- Weekly summaries.
- Activity analytics.
- Comparison between plans and actual activity.

Planned route:

```text
/activity/
```

## Platform Routes

```text
/                                  MVS Tracker module selector
/accounts/login/                   Owner login
/accounts/logout/                  Owner logout
/anime/                            MAL Insights
/games/                            Game Kiroku dashboard
/games/library/                    Game Kiroku library
/games/library/<slug>/             Game Kiroku game detail
/games/platinum/                   Game Kiroku Platinum Collection
/games/franchises/                 Game Kiroku franchise list
/games/franchises/<slug>/          Game Kiroku franchise detail
/games/igdb/search/                Owner-only IGDB search
/games/igdb/<igdb_id>/import/      Owner-only IGDB import review
/watchroom/                        Watchroom — planned
/music/                            Music — planned
/activity/                         Hibi Log — planned
/admin/                            Django administration
```

Hibi Log will serve as the future cross-module activity dashboard, so a separate global `/dashboard/` route is not currently planned.

## Access Model

Read-only views are publicly accessible.

Actions that modify external services, Supabase, or local application data normally require:

- An authenticated user.
- A POST request.
- CSRF validation.

The MyAnimeList OAuth connect and callback routes are authenticated owner flows that use OAuth state validation and PKCE rather than normal write-form POST handling.

Opening a normal page never triggers an automatic synchronization.

## Tech Stack

- Python
- Django
- PostgreSQL
- Supabase PostgreSQL
- MyAnimeList API v2
- OAuth 2.0 with PKCE and refresh tokens
- AniList GraphQL API
- IGDB API
- Twitch application authentication for IGDB
- Last.fm API — planned
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
│   ├── test_settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── core/
│   ├── static/core/
│   ├── templates/core/
│   ├── apps.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
│
├── games/
│   ├── management/commands/
│   │   ├── backfill_completed_playthroughs.py
│   │   └── setup_competitive_presets.py
│   ├── migrations/
│   ├── services/
│   │   ├── igdb_client.py
│   │   ├── igdb_importer.py
│   │   ├── igdb_normalizer.py
│   │   └── playthrough_state.py
│   ├── static/games/
│   ├── templates/games/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── detail.html
│   │   ├── franchise_detail.html
│   │   ├── franchise_list.html
│   │   ├── igdb_import.html
│   │   ├── igdb_search.html
│   │   ├── library.html
│   │   └── platinum.html
│   ├── web/
│   │   ├── dashboard.py
│   │   ├── detail.py
│   │   ├── franchise.py
│   │   ├── igdb.py
│   │   ├── library.py
│   │   └── platinum.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   └── urls.py
│
├── mal_data/
│   ├── management/commands/
│   ├── migrations/
│   ├── services/
│   │   ├── anime_list_sync.py
│   │   ├── anilist_airing_sync.py
│   │   ├── episode_signal_sync.py
│   │   ├── mal_client.py
│   │   ├── mal_oauth.py
│   │   ├── manual_tracked_sync.py
│   │   └── ...
│   ├── static/mal_data/
│   ├── web/
│   │   ├── dashboard.py
│   │   ├── library.py
│   │   ├── oauth.py
│   │   ├── relations.py
│   │   ├── search.py
│   │   ├── seasonal.py
│   │   └── sync.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   └── urls.py
│
├── templates/
│   ├── registration/
│   ├── mal_data/
│   └── base.html
│
├── docs/
│   └── game-kiroku-data-model.md
│
├── manage.py
├── requirements.txt
└── README.md
```

The technical Django app name `mal_data` is intentionally preserved to avoid unnecessary migration and database table changes. Its public module name is **MAL Insights**.

Watchroom, Music, and Hibi Log do not yet have Django apps. Their selector cards define the platform roadmap without introducing unused database structures.

## Environment Variables

Create a `.env` file in the project root.

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=postgresql://...

MAL_CLIENT_ID=your-mal-client-id
MAL_CLIENT_SECRET=your-mal-client-secret
MAL_REDIRECT_URI=http://127.0.0.1:8000/anime/oauth/mal/callback/

IGDB_CLIENT_ID=your-twitch-client-id
IGDB_CLIENT_SECRET=your-twitch-client-secret

ALLOWED_HOSTS=127.0.0.1,localhost
```

MyAnimeList access and refresh tokens are obtained through the owner-only OAuth flow and stored in the database. A permanent `MAL_ACCESS_TOKEN` is no longer required in `.env`.

The Redirect URL configured in the MyAnimeList API client must match `MAL_REDIRECT_URI` exactly, including host, port, path, and trailing slash.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

After logging in as the owner, use **Connect / Renew MAL** once to authorize the application. Future MAL access-token expiration is handled automatically through the stored refresh token.

## MAL Insights Synchronization

### Sync MAL Library

Fetches the five MAL anime-list statuses and updates the local archive.

The sync loads existing records in bulk, compares relevant fields in memory, and writes only entries that actually changed.

A normal result may look like:

```text
Total: 675
Created: 0
Updated: 1
Unchanged: 674
```

### Sync Signals

Processes only locally active Watching and Rewatching entries, regardless of whether they came from the normal MAL list endpoint or a manual rescue.

For each active entry it:

- Reads the real personal status and progress from MAL.
- Updates local progress, score, and rewatch state.
- Keeps active manual trackers aligned.
- Creates Command Log events for relevant changes.
- Refreshes AniList airing data.
- Recalculates aired, pending, and next-episode information.

### Sync Manual Rescues

Refreshes active `ManualTrackedAnime` records and reconstructs their local `AnimeEntry` data when necessary.

This workflow exists for rare cases where an anime appears in the user's real MAL list but is omitted by the normal MAL list API response.

### Rescue an omitted anime

```bash
python manage.py rescue_anime_entry MAL_ID   --status watching   --episodes-watched 1   --sync-airing
```

The rescue command creates or updates the local anime entry, stores a persistent manual tracker, and optionally retrieves AniList airing information.

After the initial rescue, normal progress updates for active rescued anime are handled by **Sync Signals**.

## Game Kiroku Maintenance Commands

### Backfill completed playthrough history

Preview completed entries that still lack playthrough history:

```bash
python manage.py backfill_completed_playthroughs --dry-run
```

Create one completed historical playthrough for every eligible entry:

```bash
python manage.py backfill_completed_playthroughs
```

The command is idempotent. Entries that already have playthroughs are skipped.

### Install competitive presets

Preview or apply the Rocket League configuration:

```bash
python manage.py setup_competitive_presets \
  --game "Rocket League" \
  --preset rocket-league \
  --dry-run

python manage.py setup_competitive_presets \
  --game "Rocket League" \
  --preset rocket-league
```

Apply REDSEC ranks to the existing Battlefield 6 library entry:

```bash
python manage.py setup_competitive_presets \
  --game "Battlefield 6" \
  --preset redsec
```

The preset command preserves existing history, creates missing modes and tiers, normalizes preset ordering, supports dry runs, and can be executed repeatedly without creating duplicates.

## Running Tests

MVS Tracker uses an isolated SQLite in-memory database for automated tests.

```bash
python manage.py test \
  core \
  mal_data \
  games \
  --settings=config.test_settings \
  --verbosity=2
```

The test database is created and destroyed automatically. It does not modify Supabase.

At the current project checkpoint, the automated suite contains **158 passing tests**.

The MAL Insights regression suite covers:

- Public and protected routes.
- OAuth token exchange and storage.
- Automatic refresh of expired MAL tokens.
- A single refresh and retry after a MAL 401 response.
- Created, Updated, and Unchanged MAL Library synchronization paths.
- Watching, Rewatching, and manual-rescue Episode Signal selection.
- Progress synchronization and Command Log generation.
- Manual rescue synchronization from real MAL progress.

The Game Kiroku regression suite covers:

- Public routes and owner-only write actions.
- Dashboard, library, detail, Platinum Collection, and franchise views.
- Platinum dates, targets, filters, ordering, and model validation.
- Franchise visibility, creation, editing, safe deletion, assignment, movement, removal, and timeline ordering.
- Library-entry and playthrough state synchronization.
- Playthrough creation, editing, transitions, numbering, dates, and access validation.
- Access creation, editing, duplicate prevention, historical locking, and safe deletion.
- IGDB import-form validation and franchise selection.
- Automatic completed-playthrough creation during IGDB import.
- Historical completed-playthrough backfill and dry-run behavior.
- Competitive mode, tier, record, division, ordering, and cross-game validation.
- Owner-only competitive CRUD, archived-mode behavior, protected deletion, and current-rank fallback.
- Lazy tier-editor rendering for large configurations.
- Rocket League and REDSEC preset creation, normalization, dry runs, history preservation, and idempotence.

## Data Sources

### MyAnimeList

Primary source for personal anime and manga list data.

MyAnimeList OAuth credentials are handled through an owner-authorized flow. Access and refresh tokens are stored in Supabase, access tokens are renewed automatically before expiration, and a failed API request caused by an invalid access token is retried once after a forced refresh.

### AniList

Public metadata and discovery source for airing data, native titles, streaming links, seasonal anime, and search.

### IGDB

Primary metadata and relationship source for Game Kiroku.

IGDB is used through explicit owner actions to:

- Search for games.
- Review the correct title or edition.
- Link metadata to an existing local record.
- Create a new local library record.
- Refresh stored metadata.
- Detect DLC, expansions, standalone expansions, and parent-game relationships.

Imported metadata and raw payloads are stored locally in Supabase. Normal page loads do not require an IGDB request.

### Last.fm

Planned primary listening-data source for the music module. Music will be the final module developed.

## Development Principles

- One Django project containing multiple connected modules.
- Four domain trackers connected through Hibi Log.
- Shared authentication and database.
- Public reading, private writing.
- Local-first storage for imported metadata.
- Explicit synchronization instead of hidden writes during page loads.
- Semantic HTML when appropriate.
- Services separated from HTTP views.
- Modules organized by domain.
- External APIs treated as import and synchronization sources, not permanent runtime dependencies.
- Automated tests use an isolated in-memory database and never modify Supabase.

## Roadmap

### Platform Foundation

- [x] Create the MVS Tracker module selector.
- [x] Move MAL Insights under `/anime/`.
- [x] Add Game Kiroku under `/games/`.
- [x] Add shared authentication.
- [x] Add public read-only mode.
- [x] Protect write actions with login and POST.
- [x] Remove synchronization side effects from GET requests.
- [x] Modularize MAL Insights views.
- [x] Add automated access and route tests.
- [x] Define the four-tracker and Hibi Log architecture.
- [ ] Build Hibi Log as the cross-module activity dashboard.

### Game Kiroku

- [x] Create the Django app.
- [x] Add the module dashboard and navigation.
- [x] Define library, access, playthrough, and additional-content models.
- [x] Add the Game Kiroku admin.
- [x] Build the dynamic dashboard.
- [x] Build the searchable and filterable library.
- [x] Add wishlist and access modeling.
- [x] Add platinum tracking at library-entry level.
- [x] Add platinum acquisition dates and Platinum Targets.
- [x] Add the dedicated Platinum Collection.
- [x] Add Platinum Unlocked and Platinum Target library filters.
- [x] Add replay-aware completion analytics.
- [x] Add the individual game detail page.
- [x] Add owner editing controls.
- [x] Integrate IGDB search, import, linking, and refresh actions.
- [x] Store IGDB metadata locally.
- [x] Add exact-title-first IGDB result ranking.
- [x] Add additional-content tracking for DLC and expansions.
- [x] Detect IGDB DLC, expansion, standalone-expansion, and parent-game relations.
- [x] Allow related content to be tracked under a game or imported separately.
- [x] Add manual additional-content records.
- [x] Protect platinum entries from losing their final Owned access.
- [x] Add public franchise list and detail views.
- [x] Add franchise logos and dynamic representative artwork.
- [x] Add franchise creation, editing, safe deletion, and game assignment.
- [x] Add reversible franchise release-timeline ordering.
- [x] Add manual competitive-rank tracking per game and mode.
- [x] Add completed-import playthrough creation and historical backfill.
- [x] Add competitive presets for Rocket League and REDSEC.
- [x] Complete the final responsive, empty-state, navigation, and documentation review.
- [x] Mark the Game Kiroku MVP as complete.
- [ ] Add an optional full-entry deletion workflow after the MVP.
- [ ] Expand game analytics after the MVP.
- [ ] Connect Game Kiroku activity to Hibi Log.

### Watchroom

- [x] Define the module name and descriptor.
- [ ] Create the Django app.
- [ ] Define its media and library models.
- [ ] Build the Series & Movies library.
- [ ] Add progress and rewatch tracking.
- [ ] Connect activity to Hibi Log.

### Music

- [ ] Select the final module name.
- [ ] Create the Django app.
- [ ] Integrate Last.fm.
- [ ] Build artist, album, and track views.
- [ ] Add listening-period analytics.
- [ ] Connect music activity to Hibi Log.

### Hibi Log

- [x] Define Hibi Log as the cross-module activity layer.
- [ ] Define the shared activity-session model.
- [ ] Connect sessions to MAL Insights.
- [ ] Connect sessions to Game Kiroku.
- [ ] Connect sessions to Watchroom.
- [ ] Connect summaries to Music.
- [ ] Build the daily calendar.
- [ ] Add weekly summaries.
- [ ] Add activity analytics.

### MAL Insights

- [x] Add automatic MyAnimeList OAuth token renewal.
- [x] Add one-time forced refresh and retry after MAL 401 responses.
- [x] Split MAL Library, Episode Signals, and Manual Rescue synchronization.
- [x] Optimize MAL Library synchronization to skip unchanged entries.
- [x] Unify Episode Signals for normal Watching, Rewatching, and manual rescues.
- [x] Synchronize active Episode Signal progress directly from MAL.
- [x] Generate Command Logs for rescued-entry progress changes.
- [x] Add persistent manual rescue fallbacks for MAL list API omissions.
- [x] Add regression tests for OAuth and synchronization workflows.
- [ ] Expand manga support.
- [ ] Add manga archive views.
- [ ] Explore chapter availability signals.
- [ ] Detect when a manually rescued anime begins appearing normally in the MAL list API.
- [ ] Improve entries without confirmed MAL IDs.

## Security

Never commit:

- `.env`
- Database credentials
- MAL client secrets
- MAL access tokens
- MAL refresh tokens
- IGDB client secrets
- API tokens
- Raw private API responses
- Local virtual environments
- Local database files
- Collected static output

## License

No license has been selected yet.
