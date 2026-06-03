# Backend Schema Document

**Project:** Shazam Clone  
**Version:** 1.0  
**Date:** June 2026  
**Database:** Supabase (PostgreSQL)

---

## Overview

All user data is stored in Supabase PostgreSQL. Authentication is handled by Supabase Auth (`auth.users` table — managed automatically). The application uses two custom tables in the `public` schema: `profiles` and `recognition_history`. Row-Level Security (RLS) is enabled on all custom tables.

---

## Schema Diagram

```
auth.users (managed by Supabase)
    │
    │ id (UUID) — 1:1
    ▼
public.profiles
    │
    │ id (UUID) — 1:N
    ▼
public.recognition_history
```

---

## Table Definitions

---

### `auth.users` (Supabase Managed)

Automatically created and managed by Supabase Auth. Never write to this directly.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `uuid` | Primary key |
| `email` | `text` | User's email |
| `created_at` | `timestamptz` | Account creation timestamp |

Referenced by `profiles.id` as a foreign key.

---

### `public.profiles`

Extends `auth.users` with application-specific data. Created automatically via a database trigger when a new user registers.

```sql
create table public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  display_name  text,
  avatar_url    text,
  save_history  boolean      not null default true,
  created_at    timestamptz  not null default now(),
  updated_at    timestamptz  not null default now()
);
```

| Column | Type | Nullable | Default | Description |
|--------|------|:--------:|---------|-------------|
| `id` | `uuid` | ❌ | — | FK to `auth.users.id`; PK |
| `display_name` | `text` | ✅ | `null` | Optional display name |
| `avatar_url` | `text` | ✅ | `null` | Profile picture URL |
| `save_history` | `boolean` | ❌ | `true` | User preference: auto-save recognized songs |
| `created_at` | `timestamptz` | ❌ | `now()` | Row creation time |
| `updated_at` | `timestamptz` | ❌ | `now()` | Last update time (auto-updated via trigger) |

**Trigger — auto-create profile on signup:**
```sql
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id)
  values (new.id);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
```

**Trigger — auto-update `updated_at`:**
```sql
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();
```

---

### `public.recognition_history`

Stores every song recognition event for an authenticated user.

```sql
create table public.recognition_history (
  id              uuid         primary key default gen_random_uuid(),
  user_id         uuid         not null references public.profiles(id) on delete cascade,
  song_title      text         not null,
  artist          text         not null,
  album           text,
  genre           text,
  release_year    smallint,
  album_art_url   text,
  spotify_url     text,
  apple_music_url text,
  raw_api_data    jsonb,
  recognized_at   timestamptz  not null default now()
);
```

| Column | Type | Nullable | Default | Description |
|--------|------|:--------:|---------|-------------|
| `id` | `uuid` | ❌ | `gen_random_uuid()` | Primary key |
| `user_id` | `uuid` | ❌ | — | FK to `profiles.id` |
| `song_title` | `text` | ❌ | — | Song name returned by API |
| `artist` | `text` | ❌ | — | Primary artist name |
| `album` | `text` | ✅ | `null` | Album name (may be null if unknown) |
| `genre` | `text` | ✅ | `null` | Music genre |
| `release_year` | `smallint` | ✅ | `null` | 4-digit year |
| `album_art_url` | `text` | ✅ | `null` | URL to album cover image |
| `spotify_url` | `text` | ✅ | `null` | Deep link to Spotify track |
| `apple_music_url` | `text` | ✅ | `null` | Deep link to Apple Music track |
| `raw_api_data` | `jsonb` | ✅ | `null` | Full API response blob (for future use) |
| `recognized_at` | `timestamptz` | ❌ | `now()` | When recognition occurred |

**Indexes:**
```sql
-- Primary lookup: user's history, newest first
create index idx_recognition_history_user_time
  on public.recognition_history(user_id, recognized_at desc);

-- For searching by song title (future feature)
create index idx_recognition_history_title
  on public.recognition_history using gin(to_tsvector('english', song_title || ' ' || artist));
```

---

## Row-Level Security (RLS)

RLS ensures users can only access their own data. Every table has RLS enabled.

### `profiles` RLS

```sql
alter table public.profiles enable row level security;

-- Users can read only their own profile
create policy "profiles: select own"
  on public.profiles
  for select
  using (auth.uid() = id);

-- Users can update only their own profile
create policy "profiles: update own"
  on public.profiles
  for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Insert is handled only by the trigger (no user direct insert)
```

### `recognition_history` RLS

```sql
alter table public.recognition_history enable row level security;

-- Users can read only their own history
create policy "history: select own"
  on public.recognition_history
  for select
  using (auth.uid() = user_id);

-- Users can insert only rows with their own user_id
create policy "history: insert own"
  on public.recognition_history
  for insert
  with check (auth.uid() = user_id);

-- Users can delete only their own rows
create policy "history: delete own"
  on public.recognition_history
  for delete
  using (auth.uid() = user_id);
```

---

## API Data Flow

### Saving a recognized song

1. Client receives song match from `/api/recognize`
2. Client calls `/api/history` (POST) with JWT in Authorization header
3. Serverless function verifies JWT via `supabase.auth.getUser(token)`
4. Function inserts row into `recognition_history` with the user's `user_id`
5. Returns the newly created row (with `id`) to client

### Fetching history

1. Client calls `/api/history` (GET) with JWT
2. Function queries:
```sql
select id, song_title, artist, album, album_art_url, recognized_at
from recognition_history
where user_id = $1
order by recognized_at desc
limit 20 offset $2;
```
3. Returns paginated array of history items

---

## Storage (Supabase Storage)

Not used in v1. Reserved for future use (user-uploaded avatars).

**Planned bucket structure (v2):**
```
avatars/
  {user_id}/
    avatar.webp
```

---

## Data Retention & Deletion

- When a user deletes their account (`DELETE /api/account`):
  1. Delete all rows in `recognition_history` where `user_id = auth.uid()`
  2. Delete row in `profiles` where `id = auth.uid()`
  3. Call `supabase.auth.admin.deleteUser(userId)` via service role key
  - Cascade deletes handle steps 1–2 automatically via `on delete cascade` FK constraints

- Users can delete individual history items at any time
- Users can delete all history via Settings (bulk delete)

---

## Environment Configuration

| Variable | Used in | Purpose |
|----------|---------|---------|
| `VITE_SUPABASE_URL` | Frontend | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Frontend | Public anon key (safe to expose; RLS enforces security) |
| `SUPABASE_URL` | Serverless functions | Same URL, server-side |
| `SUPABASE_SERVICE_ROLE_KEY` | Serverless functions only | Admin operations (never expose to client) |

