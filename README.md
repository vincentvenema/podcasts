# Marvin's Picks

Static site tracking Marvin Jacobs' weekly "Podcast voor de Week" recommendations.
Live at https://vincentvenema.com/podcasts/.

## How it works

- `index.html` reads `podcasts.json` at runtime (with an inline fallback copy). Two
  tabs: Podcast voor de Week and Beste van 2025.
- `podcasts.json` is the source of truth.
- Every Monday a single GitHub Action checks Adformatie's public dossier for a new
  pick, looks the show up on Spotify, and fills the entry from Spotify (description,
  link, publisher) when the title is a confident match. It then commits to `main`
  and deploys to Hostinger over FTP. No AI, no review step.
- Picks that are not on Spotify (or with no confident match) are skipped and retried
  next run. Add those by hand: editing `podcasts.json` on GitHub redeploys on its own.

## Files

```
index.html, podcasts.json, assets/, sitemap.xml, robots.txt   the site
scripts/update_podcasts.py   finds new picks, fills them from Spotify
scripts/sync_inline.py       rewrites the inline fallback to match podcasts.json
.github/workflows/update-podcasts.yml   Monday check, commit and deploy in one job
```

## One-time setup on GitHub

1. Repo secrets (Settings, Secrets and variables, Actions):
   - `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD` (Hostinger FTP details)
   - `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` (free app at developer.spotify.com/dashboard)
2. Confirm `server-dir` in the workflow matches where the site sits on Hostinger
   (default `/public_html/podcasts/`).
3. Actions tab, run "Update and publish podcast picks" once to verify.

## Notes

- The description is Spotify's own text (trimmed of promo lines), not a rewrite, so
  length and language vary. "Makers" is the Spotify publisher. Category is left blank.
- It publishes straight to the live site with no review, so an occasional rough or
  mismatched entry can appear until you edit it.
