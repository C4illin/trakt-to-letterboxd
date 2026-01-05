# Letterboxd Trakt Sync

Automatically sync your Trakt movies to Letterboxd:

- Export your ratings and watch history from Trakt
- Auto-import to Letterboxd (with Selenium)
- Detect rewatches
- Convert ratings from 0-10 to 0-5 scale
- Incremental sync (only new movies)

## 🚀 Quick Start

### 1. Configuration

Duplicate `config.template.yml` to `config.yml` at the root:

```yaml
letterboxd_username: your_username
letterboxd_password: your_password
trakt_client_id: your_client_id
trakt_client_secret: your_client_secret

# internal is filled automatically - do not edit manually
internal:
  trakt_oauth:
    token:
    refresh:
    expires_at:
  last_successful_run:
```

To get `trakt_client_id` and `trakt_client_secret`:
- Go to https://trakt.tv/oauth/applications/new
- Name: `letterboxd-trakt-sync`
- Redirect URI: `urn:ietf:wg:oauth:2.0:oob`

### 2. First Run (Authentication)

With docker-compose:
```bash
make setup
make run
```

**Without Docker (directly with Python):**
```bash
make setup_dev
make dev
```
Trakt Device Authentication
Visit https://trakt.tv/activate and enter the code shown below.

On first run, you'll see an activation code:
```
Your user code is: ABCD1234
Navigate to https://trakt.tv/activate
```
Go to the link and enter the code. Once authenticated, tokens are saved to `config.yml`.

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULED` | `false` | Enable scheduled runs with cron |
| `CRON_SCHEDULE` | `0 * * * *` | Cron schedule (default: hourly) |
| `RUN_ON_START` | `false` | Run immediately on startup |
| `AUTO_IMPORT` | `false` | Auto-import to Letterboxd after export |
| `HEADLESS_IMPORT` | `true` | Run Selenium in headless mode |
| `TZ` | - | Timezone (e.g., `Europe/Zurich`) |

### Docker Compose Example

```yaml
services:
  trakt-to-letterboxd:
    image: louiscrc/trakt-to-letterboxd:latest
    environment:
      - SCHEDULED=true
      - CRON_SCHEDULE=0 0 * * *  # Daily at midnight
      - RUN_ON_START=true
      - AUTO_IMPORT=true
      - HEADLESS_IMPORT=true
      - TZ=Europe/Paris
    volumes:
      - ./config.yml:/app/config/config.yml
      - ./csv:/csv
    restart: unless-stopped
```

## 📁 Generated Files

CSV files are created in the `csv/` folder:

| File | Description |
|------|-------------|
| `export.csv` | New movies only (to import to Letterboxd) |
| `merged.csv` | Full history of all your movies |
| `ratings.csv` | Your Trakt ratings |
| `watched.csv` | Your Trakt watch history |

Format: `Title,Year,Rating10,Rewatch,imdbID,WatchedDate`

## 📝 Notes

- Auto-import requires Chrome (included in Docker, headless mode only)
- Letterboxd password is required for auto-import
- Trakt tokens are automatically saved and refreshed in `config.yml`
- Only new movies are imported on each run (incremental sync)
