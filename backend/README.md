# DesktopWidgets backend

A small Cloudflare Worker with a D1 (SQLite) database. It stores:

- **installs**: one row per installation (random ID, country, version, last seen)
- **feedback**: ratings and comments from the in-app feedback card

Cloudflare tells the Worker which country each request comes from, so the app
never has to send location and the IP address is never stored. The free plan
covers this comfortably (100k requests/day, 5 GB of D1 storage).

## One-time setup

You need a free Cloudflare account and Node.js.

```bat
cd backend
npx wrangler login
npx wrangler d1 create desktopwidgets
```

Copy the `database_id` it prints into `wrangler.toml`, then create the tables
and deploy:

```bat
npx wrangler d1 execute desktopwidgets --remote --file=schema.sql
npx wrangler secret put ADMIN_TOKEN
npx wrangler deploy
```

For `ADMIN_TOKEN`, type any long random string; it protects `/stats`.
`deploy` prints your URL, for example
`https://desktopwidgets-api.<you>.workers.dev`. Put that URL in
`TELEMETRY_URL` in `desktop_widgets/services/telemetry.py` and release
(this project uses `https://desktopwidgets-api.cenker-dw.workers.dev`).
Until that is set, the app sends nothing and never shows the feedback card.

## Seeing your numbers

Open **https://desktopwidgets-api.cenker-dw.workers.dev/dashboard** in any
browser (phone too). It asks for your `ADMIN_TOKEN` once and keeps it in that
browser only; "Forget token" removes it. It shows total installs, active users
(7 and 30 days), users per country, versions, ratings and the latest feedback.
The page itself contains no data; everything is loaded from `/stats` with the
token.

Everything at once (users per country, active users, versions, ratings, the
latest 50 comments):

```bat
curl -H "Authorization: Bearer <ADMIN_TOKEN>" https://desktopwidgets-api.<you>.workers.dev/stats
```

Or run any SQL yourself:

```bat
npx wrangler d1 execute desktopwidgets --remote --command "SELECT country, COUNT(*) AS users FROM installs GROUP BY country ORDER BY users DESC"
npx wrangler d1 execute desktopwidgets --remote --command "SELECT created_at, rating, text FROM feedback ORDER BY created_at DESC LIMIT 20"
```

The same queries work in the Cloudflare dashboard under
**Storage & Databases → D1 → desktopwidgets → Console**.

"Active" means the app pinged in that window. Users who switch off usage stats
in data.json stop pinging, so treat the counts as a lower bound.

## When the app asks for feedback

Defined in `desktop_widgets/services/telemetry.py`:

- first time: after 14 days of use **and** at least 3 updates
- after that: at most once every 90 days
- "Don't ask again" stops it for good
- it appears 3 minutes after launch, never on top of another dialog

## Testing locally

```bat
npx wrangler d1 execute desktopwidgets --local --file=schema.sql
npx wrangler dev
set DESKTOPWIDGETS_TELEMETRY_URL=http://127.0.0.1:8787
python main.py
```
