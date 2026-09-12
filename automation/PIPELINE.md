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
   among what's left (if everything is excluded, pick the least recently used).
4. **Pick a base image**: exclude images used in the last
   `avoid_repeat_image_within_posts` posts; pick randomly among what's left.
5. **Write the content** (in Russian, matching the theme):
   - `movies`: 4–6 *real* movie titles that genuinely fit the theme — use your
     own knowledge, don't invent titles. Exclude titles used for this same
     theme in the last `avoid_repeat_movie_within_posts` posts.
   - `overlay_title`: short punchy headline for the image (can be the theme
     itself or a tighter rewrite of it).
   - `caption`: 1–3 engaging sentences for the TikTok description.
   - `hashtags`: 5–8 relevant hashtags (mix of broad movie/cinema tags and
     theme-specific ones).
   - Combine `caption` + `hashtags` into one string ≤ `caption_max_length`
     chars (TikTok's title field limit is 150) — trim the caption first if
     it doesn't fit, never the hashtags to zero.
6. **Render the image**:
   ```
   pip install -q -r automation/requirements.txt
   python3 automation/compose_post.py \
     --image "<chosen base image URL>" \
     --title "<overlay_title>" \
     --movies "<movie1>|<movie2>|..." \
     --out /tmp/tiktok_post.jpg
   ```
7. **Host the final image**: `mcp__higgsfield__media_upload` (presigned URL
   flow) with `/tmp/tiktok_post.jpg`, PUT the bytes, then
   `mcp__higgsfield__media_confirm`. Use the resulting hosted URL for
   publishing — TikTok requires a Higgsfield-hosted asset.
8. **Get the connector**: `mcp__higgsfield__tiktok_accounts` → the `active`
   account's `connector_id`.
9. **Prepare + publish** (settings from `automation/config.json` `publish`
   block):
   - `mcp__higgsfield__tiktok_prepare_publish` with `media_type: PHOTO`,
     `mode: DIRECT_POST`, `photo_images: [hosted_url]`, `title` = the combined
     caption+hashtags string, and the `publish` defaults from config.
   - Set every flag in the response's `required_confirmations` to `true` and
     call `mcp__higgsfield__tiktok_publish` with the same `publish_session_id`,
     `connector_id`, `media_type: PHOTO`, `mode: DIRECT_POST`,
     `user_confirmed: true`, `preview_confirmed: true`.
10. Optionally poll `mcp__higgsfield__tiktok_publish_status` once or twice to
    confirm it left `PROCESSING_DOWNLOAD`.
11. **Log the post**: append to `automation/posts_log.json`:
    ```json
    {
      "date": "<ISO date>",
      "theme": "<theme>",
      "movies": ["..."],
      "image_used": "<base image id/url>",
      "caption": "<caption>",
      "hashtags": ["..."],
      "publish_id": "<publish_id>"
    }
    ```
12. Commit and push the updated `posts_log.json` to the branch this repo is
    developed on, message: `chore: log post <date>`.

## Failure handling

If any step fails (no active account, prepare/publish rejected, image
composition error), **do not** write a log entry for it, and report the
failure plainly instead of retrying silently. A missed post is better than a
broken/duplicate one.
