# Movie post pipeline

Runs every 2 days via a scheduled Routine. This file is the source of truth for
what the fired session must do — the Routine prompt just points here so the
pipeline can be edited without recreating the trigger.

## Preconditions

- `mcp__higgsfield__tiktok_accounts` must return one `active` account. If not,
  stop and report — do not silently skip a post.
- `automation/base_images.json` must have at least one image entry.

## Steps

1. Pull the latest of this repo/branch.
2. Read `automation/themes.json`, `automation/posts_log.json`,
   `automation/base_images.json`, `automation/config.json`.
3. **Pick a theme**: exclude any theme used in the last
   `avoid_repeat_theme_within_posts` entries of `posts_log.json`; pick randomly
   among what's left (if everything is excluded, pick the least recently
   used). Each theme entry carries a `font_style` — this decides which
   headline font is used later.
4. **Pick the image for the post**: exactly one (`config.images_per_post` is
   `1` — TikTok gets a single photo, never a carousel), excluding images used
   in the last `avoid_repeat_image_within_posts` posts; pick randomly among
   what's left. This is the **hero** image — it gets the headline overlay.
5. **Write the content** (in Russian, matching the theme):
   - `movies`: exactly `config.movies_per_post` (10) *real* movie titles with
     release year that genuinely fit the theme — use your own knowledge,
     don't invent titles. Exclude titles used for this same theme in the last
     `avoid_repeat_movie_within_posts` posts. For each, write **exactly 3
     tight sentences** — what it's about, why it fits the theme, why it's
     worth watching — TikTok-caption pace, not a review essay:
     - cut filler and throat-clearing ("действительно", "по-настоящему",
       redundant adjectives); every word should earn its place
     - no repeating the same idea twice across the 3 sentences
     - after a first draft, reread and cut ~25-30% of the words without
       losing meaning — a caption that reads noticeably slower than a
       TikTok comment is too long
     - example (too padded → tightened):
       "Городской парень и деревенская девушка внезапно начинают меняться
       телами и постепенно влюбляются друг в друга, даже не встретившись
       лично. За красивой анимацией и фантастическим сюжетом скрывается
       очень настоящая история про первую любовь и взросление через
       принятие ответственности. Одна из самых красивых работ в
       современной анимации." →
       "Городской парень и деревенская девушка внезапно начинают меняться
       телами и влюбляются друг в друга, даже не встретившись лично. За
       фантастическим сюжетом скрывается история первой любви, взросления
       и ответственности. Одна из самых красивых работ современной
       анимации."
   - `overlay_title`: short, catchy headline for the hero image — this is
     also what goes in the TikTok `title` field (≤ `title_max_length`
     chars). Think hook, not label (e.g. "Я бы стёр себе память, чтобы ещё
     раз посмотреть эти фильмы" rather than a plain theme name).
   - `description`: the full TikTok caption (≤ `description_max_length`
     chars), built as:
     ```
     <overlay_title>

     1. <Movie 1> (<year>)
     <3+ sentence paragraph: what it's about, why it fits, why watch it>

     2. <Movie 2> (<year>)
     <3+ sentence paragraph: what it's about, why it fits, why watch it>

     ...

     <one closing line / call to action>

     <hashtags, 5-8, space separated>
     ```
     If `config.location_text` is set, append it as the last line — this is
     plain decorative text, **not** a real geotag (see Known limitations).
     If the total doesn't fit `description_max_length`: trim the closing
     line first, then shorten the per-movie paragraphs (never below 3
     sentences), and only as a last resort drop the lowest-priority
     hashtags — never all of them.
6. **Render the image**:
   ```
   pip install -q -r automation/requirements.txt
   python3 automation/compose_post.py hero \
     --image "<hero image URL>" \
     --title "<overlay_title>" \
     --font-style "<theme's font_style>" \
     --out /tmp/tiktok_post.jpg
   ```
7. **Host the final image**: `mcp__higgsfield__media_upload` (presigned URL
   flow), PUT the bytes, then `mcp__higgsfield__media_confirm`. Use the
   resulting hosted URL — TikTok requires a Higgsfield-hosted asset.
8. **Get the connector**: `mcp__higgsfield__tiktok_accounts` → the `active`
   account's `connector_id`.
9. **Pick music** (skip this step if `config.music.enabled` is `false`):
   look up the theme's `font_style` in `config.music.genre_by_font_style` to
   get a TikTok CML genre, then call `mcp__higgsfield__tiktok_music_trending`
   with that `genre`, `config.music.country_code`, `config.music.date_range`.
   Exclude `song_clip_id`s used in the last `avoid_repeat_track_within_posts`
   posts (see `posts_log.json`'s `music` field); pick randomly among what's
   left (don't always take rank 1 — vary it). Keep the track's `song_clip_id`,
   `name` and `artist` for the publish call and the log entry. If the lookup
   fails or returns nothing, proceed without music rather than blocking the
   post.
10. **Prepare + publish** (settings from `automation/config.json` `publish`
    block):
    - `mcp__higgsfield__tiktok_prepare_publish` with `media_type: PHOTO`,
      `mode: DIRECT_POST`, `photo_images: [hosted_url]` (single image),
      `title` = `overlay_title` (≤150 chars), `description` = the full caption
      built in step 5, and the `publish` defaults from config.
    - Set every flag in the response's `required_confirmations` to `true` and
      call `mcp__higgsfield__tiktok_publish` with the same `publish_session_id`,
      `connector_id`, `media_type: PHOTO`, `mode: DIRECT_POST`,
      `user_confirmed: true`, `preview_confirmed: true`, same `title` and
      `description`, plus `music_sound_id` = the picked track's `song_clip_id`
      (omit entirely if step 9 was skipped or came up empty) and
      `music_usage_confirmed: true`.
11. Optionally poll `mcp__higgsfield__tiktok_publish_status` once or twice to
    confirm it left `PROCESSING_DOWNLOAD`.
12. **Log the post**: append to `automation/posts_log.json`:
    ```json
    {
      "date": "<ISO date>",
      "theme": "<theme>",
      "font_style": "<font_style>",
      "movies": ["..."],
      "image_used": "<id>",
      "title": "<overlay_title>",
      "description": "<full caption>",
      "music": { "song_clip_id": "<id>", "name": "<track name>", "artist": "<artist>" },
      "publish_id": "<publish_id>"
    }
    ```
    Omit `music` (or set it to `null`) if no track was attached.
13. Commit and push the updated `posts_log.json` to the branch this repo is
    developed on, message: `chore: log post <date>`.

## Known limitations

- **No native location tag.** TikTok's Content Posting API (and Higgsfield's
  wrapper) has no location/POI parameter — `config.location_text`, if set, is
  only plain text appended to the caption, not a real geotag.
- **No analytics feedback yet.** Theme rotation is round-robin/random with
  cooldowns, not based on view/like/comment performance. See the README's
  "Фаза 2" section.

## Failure handling

If any step fails (no active account, prepare/publish rejected, image
composition error), **do not** write a log entry for it, and report the
failure plainly instead of retrying silently. A missed post is better than a
broken/duplicate one.
