# Game Kiroku — MVP Data Model and Architecture

This document describes the implemented state of **Game Kiroku / ゲーム記録** inside MVS Tracker.

It is no longer a pre-migration design document. The architecture documented here reflects the operational module with the schema applied through `games.0011` and a global suite of **158 passing tests**.

The MVP is complete. Its implemented functional areas are:

- Personal video game library.
- Owned and Wishlist access by platform and store.
- Playthroughs, replays, and historical completion records.
- Automatic playthrough creation for games imported as Completed.
- Idempotent backfill for older completed entries.
- Local-first IGDB metadata.
- Additional content tracking.
- Platinum Collection.
- Franchise management and release timelines.
- Competitive Rank Tracking.
- Idempotent competitive presets.
- Public read-only access.
- Authenticated owner management.
- Automated hardening through 158 tests.

---

## 1. Architecture Principles

Game Kiroku follows these principles:

- External metadata is imported and stored locally.
- IGDB is not required to render ordinary pages.
- Work metadata is separated from the user's personal relationship with that work.
- A game is not duplicated by platform.
- Ownership and Wishlist intent are represented through access records.
- Playthroughs represent individual runs.
- Progress is optional and manually recorded.
- Platinum status belongs to the full personal library entry, not to one platform.
- Franchises are organised manually.
- Competitive ranks are configured per game.
- Current competitive rank is derived from rank history.
- The MVP operates as one personal library.
- Game Kiroku models are not directly related to `User`.
- Authentication determines who can write.
- Public views are read-only.
- Mutating actions normally require login, POST, and CSRF.
- Normal GET requests do not trigger hidden synchronisation or writes.

---

## 2. Implemented Conceptual Model

```text
Franchise
    └── Game
          └── LibraryEntry
                ├── GameAccess
                │      └── Playthrough optionally
                ├── Playthrough
                ├── GameContent
                ├── CompetitiveMode
                │      └── CompetitiveRankRecord
                └── CompetitiveRankTier

CompetitiveRankRecord
    └── CompetitiveRankTier
```

### Entity Responsibilities

```text
Franchise
    Manually groups games from the same series and
    defines the franchise's visual identity.

Game
    Represents the video game as a work and stores
    local or IGDB-imported metadata.

LibraryEntry
    Represents the user's personal relationship
    with one game.

GameAccess
    Represents where the game is owned or where the
    user wants to acquire it.

Playthrough
    Represents one individual run of the game.

GameContent
    Represents DLC, expansions, and related content
    that should not count as independent library games.

CompetitiveMode
    Represents one competitive queue, mode, or discipline
    within a library entry.

CompetitiveRankTier
    Defines the rank scale and optional division system
    for one game.

CompetitiveRankRecord
    Records each historical rank update with timestamp,
    season, division, and notes.
```

---

## 3. Franchise

`Franchise` manually groups games from the same series.

Examples:

- Assassin's Creed.
- Yakuza / Like a Dragon.
- Final Fantasy.
- Persona.
- Ratchet & Clank.
- Grand Theft Auto.

A game may belong to one franchise or remain unassigned.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `name` | `CharField` | No | Unique visible name. |
| `slug` | `SlugField` | No | Stable unique URL identifier. |
| `description` | `TextField` | Yes | Optional description. |
| `logo_url` | `URLField` | Yes | Optional representative logo or image. |
| `display_order` | `PositiveIntegerField` | No | Manual ordering value. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Rules

- `name` is unique.
- `slug` is unique.
- The slug is generated once and remains stable after visible name changes.
- The relationship from `Game` is optional.
- An empty franchise can be deleted.
- A franchise with assigned games cannot be deleted.
- The owner can view and manage empty franchises.
- Anonymous visitors only see franchises that contain games.

### Visual Identity

A franchise may define a manual `logo_url`.

Its background is derived from a representative game:

```text
artwork_url
    when available

cover_url
    as fallback
```

Representative-game status priority:

```text
1. Playing
2. Completed
3. Paused
4. Multiplayer
5. Plan to Play
6. Dropped
```

When several games share the same priority, the most recently updated one is preferred.

### Routes

```text
/games/franchises/
/games/franchises/<slug>/
```

The franchise detail page includes:

- Dynamic hero image.
- Optional logo.
- Description.
- Representative game.
- Completion percentage.
- Total, Owned, Active, Plan to Play, Completed, and Platinum metrics.
- Release timeline.
- Oldest-to-newest and newest-to-oldest ordering.
- `Add Game` navigation back to Library.
- Authenticated owner controls.

---

## 4. Game

`Game` represents the video game as a work.

It does not contain personal states such as Playing, Completed, or Wishlist.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `igdb_id` | `PositiveBigIntegerField` | Yes | Unique external IGDB identifier. |
| `title` | `CharField` | No | Primary title. |
| `title_japanese` | `CharField` | Yes | Optional Japanese title. |
| `slug` | `SlugField` | No | Stable unique local identifier. |
| `summary` | `TextField` | Yes | Locally stored synopsis. |
| `cover_url` | `URLField` | Yes | Vertical cover. |
| `artwork_url` | `URLField` | Yes | Horizontal artwork or background. |
| `first_release_date` | `DateField` | Yes | Earliest known release date. |
| `igdb_main_story_hours` | `DecimalField` | Yes | Imported Main Story estimate. |
| `genres` | `JSONField` | Yes | Imported genres. |
| `platforms` | `JSONField` | Yes | Imported platforms. |
| `igdb_payload` | `JSONField` | Yes | Stored relevant IGDB payload. |
| `igdb_synced_at` | `DateTimeField` | Yes | Last explicit metadata refresh. |
| `franchise` | `ForeignKey` | Yes | Optional manual franchise. |
| `created_at` | `DateTimeField` | No | Local creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Rules

- `igdb_id` is unique when present.
- Manual games without an IGDB ID are allowed.
- `slug` is unique and stable.
- `igdb_main_story_hours` must be positive.
- Only the IGDB **Main Story** estimate is used.
- Main + Extra and Completionist estimates are outside the MVP.
- `title` has a database index.
- Library pages load from PostgreSQL, not from IGDB.
- A franchise may be assigned during import or from Game Detail.

### Local-First Import

IGDB is used only through explicit owner actions:

```text
Search
Review
Import
Link existing
Refresh metadata
Detect related content
```

The importer can:

- Link IGDB metadata to an existing local game without replacing its PK, slug, status, accesses, playthroughs, or notes.
- Transactionally create `Game`, `LibraryEntry`, and `GameAccess`.
- Automatically create `Playthrough 1` when the initial status is Completed.
- Store optional text language and completion date for that historical run.
- Assign an existing franchise during import.
- Store Platinum, Platinum date, or Platinum Target.
- Persist the IGDB payload and local sync timestamp.

---

## 5. LibraryEntry

`LibraryEntry` represents the user's personal relationship with one game.

Each `Game` can have at most one library entry.

### Implemented Statuses

```text
playing
paused
dropped
plan_to_play
completed
multiplayer
```

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `game` | `OneToOneField` | No | Associated game. |
| `status` | `CharField` | Yes | General personal status. |
| `has_platinum` | `BooleanField` | No | Platinum unlocked. |
| `platinum_earned_on` | `DateField` | Yes | Optional unlock date. |
| `is_platinum_target` | `BooleanField` | No | Future platinum goal. |
| `main_story_hours_override` | `DecimalField` | Yes | Manual duration override. |
| `notes` | `TextField` | Yes | Personal notes. |
| `created_at` | `DateTimeField` | No | Date added to the library. |
| `updated_at` | `DateTimeField` | No | Last change. |

### Status Rules

- Without playthroughs, the owner may select compatible manual statuses.
- Playing and Paused require a playthrough.
- Once playthroughs exist, library status is controlled by playthrough history.
- Multiplayer entries do not use playthroughs.
- Multiplayer entries must retain at least one Owned access.
- Multiplayer entries do not use a manual Main Story duration.

### Platinum Rules

- Platinum belongs to `LibraryEntry`, not `GameAccess`.
- Platinum requires at least one Owned access.
- `platinum_earned_on` requires `has_platinum=True`.
- A game with an unlocked platinum cannot remain a Platinum Target.
- Removing the platinum flag clears its date through the form workflow.
- A game currently owned only on PC may still be marked as a future PS5 Platinum Target.
- The final Owned access cannot be downgraded while the entry remains platinum-marked.

### Effective Duration

```text
main_story_hours_override
        when present

igdb_main_story_hours
        otherwise
```

### Derived Properties

```python
effective_main_story_hours
is_owned
is_wishlisted
```

---

## 6. Platinum Collection

The platinum system is based on `LibraryEntry`.

Route:

```text
/games/platinum/
```

The collection includes:

- Total platinum count.
- Latest platinum with a known date.
- History grouped by year.
- Platinums with unknown dates.
- Platinum Targets.
- Covers and navigation to Game Detail.

Library filters include:

```text
Platinum Unlocked
Platinum Target
```

Unlocked platinums are ordered by:

```text
newest known unlock date
        ↓
oldest known unlock date
        ↓
unknown dates last
```

---

## 7. GameAccess

`GameAccess` represents where a game is owned or where the user wants to acquire it.

The game itself is not duplicated by platform.

### Access Types

```text
owned
wishlist
```

### Implemented Platforms

```text
pc
ps5
switch_2
other
```

### Implemented Stores

```text
steam
epic_games
playstation_store
nintendo_eshop
gog
xbox
other
```

`xbox` covers the Xbox ecosystem and Game Pass access used on PC.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Associated personal entry. |
| `access_type` | `CharField` | No | Owned or Wishlist. |
| `platform_name` | `CharField` | No | Platform. |
| `store` | `CharField` | Yes | Store or ecosystem. |
| `notes` | `TextField` | Yes | Additional context. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Rules

The following exact combination is unique:

```text
library_entry
access_type
platform_name
store
```

A game may have:

- Several Owned accesses.
- Several Wishlist accesses.
- Owned and Wishlist accesses in different locations.
- Owned and Wishlist entries on the same platform when they represent distinct access intentions.

### Historical Integrity

An access referenced by a playthrough:

- Cannot be deleted.
- Must remain Owned.
- Locks access type, platform, and store.
- Still allows note editing.

This prevents retroactively rewriting the historical platform of a playthrough.

---

## 8. Playthrough

`Playthrough` represents one individual run.

### Statuses

```text
playing
paused
completed
dropped
```

### Text Languages

```text
unknown
ja
en
es
other
```

`unknown` is displayed as **Unspecified** and supports historical runs whose original text language is not remembered.

Voice language is outside the MVP.

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Personal library entry. |
| `access` | `ForeignKey` | Yes | Owned access used for this run. |
| `number` | `PositiveIntegerField` | No | Sequential run number. |
| `status` | `CharField` | No | Run status. |
| `text_language` | `CharField` | No | Primary text language. |
| `started_on` | `DateField` | Yes | Start date. |
| `finished_on` | `DateField` | Yes | Completion date. |
| `progress_note` | `CharField` | Yes | Free-form manual progress. |
| `hours_played` | `DecimalField` | Yes | Optional real playtime. |
| `notes` | `TextField` | Yes | Context or impressions. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Rules

- `number` is unique within one `LibraryEntry`.
- `number >= 1`.
- `finished_on >= started_on`.
- `hours_played > 0` when present.
- The selected access must belong to the same library entry.
- The selector only offers Owned accesses for that entry.
- A Playing or Paused run cannot have a finish date.
- Multiplayer entries do not accept playthroughs.

### Creation and State Transitions

When a new playthrough starts:

- The next number is assigned automatically.
- The local date is used when no explicit date is provided.
- Another active run from the same entry is paused.
- The `LibraryEntry` becomes Playing.

Available actions:

```text
pause
resume
complete
drop
```

Transitions update the playthrough and library entry together.

### Completed Import and Historical Backfill

When an IGDB import starts with Completed status:

- `Playthrough 1` is created automatically.
- The run is stored as Completed.
- It uses the newly created Owned access.
- Optional text language and completion date are preserved.
- Unknown language defaults to Unspecified.

Older entries marked Completed but missing playthrough history can be normalised with:

```bash
python manage.py backfill_completed_playthroughs --dry-run
python manage.py backfill_completed_playthroughs
```

The command is idempotent, skips entries with existing playthroughs, and uses an available Owned access when one exists.

### Valid Progress Examples

```text
Chapter 7
Act 2
63%
Main Story completed
```

There is no universal progress percentage or automatic completion estimate.

---

## 9. GameContent

`GameContent` tracks related content under a library entry without increasing the total game count.

### Content Types

```text
dlc
expansion
standalone_expansion
other
```

### Statuses

```text
plan_to_play
playing
paused
completed
dropped
```

### Implemented Fields

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Parent library game. |
| `igdb_id` | `PositiveBigIntegerField` | Yes | Unique external ID. |
| `title` | `CharField` | No | Content title. |
| `content_type` | `CharField` | No | Content category. |
| `status` | `CharField` | No | Personal status. |
| `summary` | `TextField` | Yes | Synopsis. |
| `cover_url` | `URLField` | Yes | Cover image. |
| `first_release_date` | `DateField` | Yes | Release date. |
| `completed_on` | `DateField` | Yes | Optional completion date. |
| `notes` | `TextField` | Yes | Personal notes. |
| `igdb_payload` | `JSONField` | Yes | Stored source payload. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

### Rules

- `igdb_id` is unique when present.
- The title is unique within the same parent game.
- `completed_on` is only valid with Completed status.
- Content may be created manually.
- Content may be created from relations detected in the stored IGDB payload.
- The owner can edit or delete tracked content.

### Detected IGDB Relations

```text
dlcs
expansions
standalone_expansions
parent_game
```

A detected work may be:

- Tracked as `GameContent`.
- Reviewed as a separate game.
- Linked to an already imported local `Game`.

---

## 10. Competitive Rank Tracking

Competitive Rank Tracking supports different game-specific ranking systems without requiring an external ranking API.

The section lives inside Game Detail and is publicly readable. Configuration, editing, and rank updates require an authenticated owner.

### 10.1 CompetitiveMode

`CompetitiveMode` represents one competitive queue or mode.

Examples:

```text
Rocket League
├── 1V1
├── 2V2
└── 3V3

Battlefield 6
└── Ranked Battle Royale
```

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Game that owns the mode. |
| `name` | `CharField` | No | Visible mode name. |
| `display_order` | `PositiveIntegerField` | No | Visual ordering value. |
| `is_active` | `BooleanField` | No | Whether new records may use the mode. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

Rules:

- Mode name is unique within one `LibraryEntry`.
- Modes are ordered by `display_order` and name.
- Archiving preserves all history.
- Archived modes disappear from new-record forms.
- A mode without history may be deleted.
- A mode with history cannot be deleted and must be archived instead.

### 10.2 CompetitiveRankTier

`CompetitiveRankTier` defines the rank scale for one game.

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `library_entry` | `ForeignKey` | No | Game that owns the rank scale. |
| `name` | `CharField` | No | Rank name. |
| `rank_order` | `PositiveIntegerField` | No | Ascending position in the scale. |
| `uses_divisions` | `BooleanField` | No | Whether the rank has divisions. |
| `division_count` | `PositiveSmallIntegerField` | Yes | Highest allowed division. |
| `created_at` | `DateTimeField` | No | Creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

Rules:

- Tier name is unique within the entry.
- `rank_order` is unique within the entry.
- A tier using divisions requires `division_count >= 1`.
- A tier without divisions requires `division_count=None`.
- A tier referenced by history cannot be deleted.
- An unused tier may be edited or deleted.
- The interface displays ranges as `Divisions I–IV` or `Divisions I–V`.

### 10.3 CompetitiveRankRecord

`CompetitiveRankRecord` represents one historical rank event.

| Field | Type | Nullable / blank | Description |
|---|---|---:|---|
| `mode` | `ForeignKey` | No | Competitive mode. |
| `rank_tier` | `ForeignKey` | No | Achieved rank. |
| `division` | `PositiveSmallIntegerField` | Yes | Current division. |
| `season` | `CharField` | Yes | Competitive season or cycle. |
| `recorded_at` | `DateTimeField` | No | Exact date and time of the record. |
| `notes` | `TextField` | Yes | Optional context. |
| `created_at` | `DateTimeField` | No | Local creation timestamp. |
| `updated_at` | `DateTimeField` | No | Last modification timestamp. |

Rules:

- Mode and tier must belong to the same `LibraryEntry`.
- Division must be positive.
- Division cannot exceed `division_count`.
- A tier without divisions rejects division values.
- Multiple updates may be recorded on the same day.
- Records are ordered by descending `recorded_at`, then descending PK.
- Current rank is always derived from the latest record.
- Deleting the latest record automatically restores the previous record as current.
- There is no separately stored `current_rank` field that can drift out of sync.

### 10.4 Owner Management and Integrity

The owner can:

- Create, edit, archive, and delete eligible modes.
- Create, edit, and delete eligible tiers.
- Create, edit, and delete rank updates.
- Correct season, timestamp, division, or notes.
- Review full history by mode.

Tier editing is lazy-loaded at the template level: all configured ranks remain visible, but only the selected tier receives a rendered edit form. This reduces HTML generation for large configurations such as Rocket League.

### 10.5 Competitive Presets

Known configurations can be installed through an idempotent management command:

```bash
python manage.py setup_competitive_presets \
  --game "Rocket League" \
  --preset rocket-league

python manage.py setup_competitive_presets \
  --game "Battlefield 6" \
  --preset redsec
```

The command also supports `--dry-run`.

Preset behaviour:

- Creates only missing modes and tiers.
- Recognises existing names without duplicating them.
- Normalises preset ordering.
- Preserves model IDs and rank history.
- Can be run repeatedly.
- Installs REDSEC inside Battlefield 6 rather than as an independent local game.

Current preset structures:

```text
Rocket League
├── 3 modes
└── 23 tiers

Battlefield 6 · REDSEC
├── 1 mode
└── 9 tiers
```

---

## 11. Constraints and Validation

### Database Constraints

Implemented constraints include:

- Unique `Game.igdb_id`.
- Unique `Game.slug`.
- Unique `Franchise.name`.
- Unique `Franchise.slug`.
- One `LibraryEntry` per `Game`.
- Positive IGDB Main Story hours.
- Positive manual duration override.
- Positive playthrough hours.
- Positive playthrough number.
- Unique playthrough number per entry.
- Valid playthrough date range.
- No duplicate exact access location.
- Unique GameContent title within its parent.
- GameContent completion date only for Completed content.
- Platinum date only when platinum is unlocked.
- Platinum Target incompatible with unlocked platinum.
- Unique competitive mode name per entry.
- Unique rank tier name per entry.
- Unique rank order per entry.
- Valid division configuration.
- Positive competitive record division.
- Competitive record index by mode and timestamp.

### Form and Service Validation

The application additionally validates:

- Playthrough access belongs to the same entry.
- Playing and Paused depend on playthroughs.
- Status and date consistency.
- Multiplayer excludes manual Main Story duration.
- Multiplayer requires an Owned access.
- Platinum requires an Owned access.
- The final Owned access of a platinum-marked game is preserved.
- Historical access identity is locked while referenced by a playthrough.
- Franchises can only be deleted when empty.
- Franchise logo URLs must be valid.
- Games may be assigned to franchises during import or later.
- Playthrough state transitions must be valid.
- Completed imports create historical playthroughs.
- Backfill skips entries with existing history.
- Competitive modes and tiers must belong to the same game.
- Division cannot exceed the tier limit.
- Archived modes cannot receive new rank records.
- Competitive history protects referenced modes and tiers from deletion.
- Mutating actions are owner-only and POST-only.

---

## 12. Django Relationships

```text
Franchise.games
Game.library_entry
Game.franchise
LibraryEntry.accesses
LibraryEntry.playthroughs
LibraryEntry.additional_contents
LibraryEntry.competitive_modes
LibraryEntry.competitive_rank_tiers
GameAccess.playthroughs
Playthrough.library_entry
Playthrough.access
GameContent.library_entry
CompetitiveMode.library_entry
CompetitiveMode.rank_records
CompetitiveRankTier.library_entry
CompetitiveRankTier.rank_records
CompetitiveRankRecord.mode
CompetitiveRankRecord.rank_tier
```

---

## 13. Main Workflows

### Import a Game from IGDB

```text
Search IGDB
        ↓
Review title and edition
        ↓
Choose status and optional franchise
        ↓
Choose initial access
        ↓
Store Game locally
        ↓
Create LibraryEntry
        ↓
Create GameAccess
        ↓
When status is Completed:
create completed Playthrough 1
```

### Link an Existing Local Game

```text
Select IGDB result
        ↓
Select local Game without IGDB link
        ↓
Update Game metadata
        ↓
Preserve PK, slug, LibraryEntry,
accesses, playthroughs, status, and notes
```

### Manage a Franchise

```text
Create Franchise
        ↓
Add description and optional logo
        ↓
Assign games from Game Detail
or during import
        ↓
Review progress and release timeline
        ↓
Move or remove games when needed
```

### Record a Playthrough

```text
Open Game Detail
        ↓
Select Owned access
        ↓
Create Playthrough
        ↓
Assign next number automatically
        ↓
Set language and date
        ↓
Update progress and state
```

### Track Additional Content

```text
Open Game Detail
        ↓
Review IGDB-detected content
        ↓
Track Under This Game
or
Review as Separate Game
```

### Record a Competitive Rank

```text
Configure mode
        ↓
Configure rank tiers
        ↓
Record rank, division,
season, and timestamp
        ↓
Derive current rank
from the latest event
```

---

## 14. Current and Future Metrics

### Implemented

- Total library count.
- Owned count.
- Wishlist count.
- Completed count.
- Plan to Play count.
- Multiplayer count.
- Platinum count.
- Franchise progress.
- Owned games per franchise.
- Completed games per franchise.
- Platinums per franchise.
- Latest platinum.
- Platinum history by year.
- Platinum Targets.
- Replay-aware completion.
- Current rank per competitive mode.
- Competitive mode and update counts.
- Rank history per mode.

### Post-MVP

- Real playtime per game and franchise.
- Estimated-versus-real duration comparisons.
- Text-language distribution.
- Advanced platform and store analytics.
- Competitive trend comparisons.
- Time-series activity connected to Hibi Log.

---

## 15. Future Hibi Log Integration

Hibi Log may relate activity to:

- `LibraryEntry`.
- `Playthrough`.
- `GameAccess` when platform context matters.
- `GameContent` when the session belongs to a DLC or expansion.
- `CompetitiveMode` when the session belongs to a ranked queue.
- `CompetitiveRankRecord` when a session ends with a rank change.

Conceptual example:

```text
ActivitySession
library_entry: Yakuza Kiwami 2
playthrough: Playthrough 2
duration_minutes: 95
progress_from: Chapter 6
progress_to: Chapter 7
notes: Main-story session in Japanese
```

Game Kiroku already exposes stable identifiers for this future integration.

---

## 16. Decisions Outside the MVP

The MVP intentionally excludes:

- Main + Extra and Completionist duration variants.
- Voice-language tracking per playthrough.
- Universal progress percentage.
- Automatic completion estimates.
- Individual trophies.
- Steam achievements.
- Physical, digital, or subscription ownership distinctions.
- Multiple users.
- Permanent background IGDB synchronisation.
- Duplicating a game by platform.
- Automatically imported franchise relationships.
- External competitive-ranking APIs.
- Automatic rank synchronisation.
- Independent playthrough and duration systems for every DLC.
- Full deletion of complex library entries with history.

---

## 17. Implementation Status

```text
Document: game-kiroku-data-model.md
Module: Game Kiroku
Stage: MVP
Status: Complete and approved
Current migration: games.0011
Global tests: 158 OK
Next main module: Watchroom
```

All MVP migrations have been created and applied. The architecture is now closed for the Watchroom phase and for later integration with Hibi Log.
