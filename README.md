# qBittorrent-sorter

## Overview

The qBittorrent-sorter is a simple script that sorts your torrents by type, such as movies, TV series, and general data. This sorting feature is particularly useful for users of media server applications like `Jellyfin`.

## Features

- **Automatic categorization**: Torrents are assigned categories based on content type:
  - `Фильм` — torrents with a single video file
  - `Сериал` — torrents with multiple video files (single season)
  - `Прочее` — torrents without video files
- **Smart path sorting**:
  - Movies → `MOVIES_PATH`
  - TV shows (single season) → `SHOWS_PATH/<Show Name>`
  - TV shows (multi-season) → `SHOWS_PATH` (no subfolder)
  - Misc → `MISC_PATH`
- **Show name extraction**: For single-season shows, the script extracts the show name from:
  1. A tag in the format `Name: <Show Name>` (if set in qBittorrent)
  2. The torrent name (with quality/resolution/season info stripped)
- **Empty directory cleanup**: Periodically removes empty folders left after torrent moves (default: once per 24 hours)

## Usage

docker-compose:

```yml
services:
  qBittorrent-sorter:
    build: .
    environment:
      TZ: "Europe/Moscow"
      QBITTORRENT_HOST: "http://192.168.0.100"
      QBITTORRENT_PORT: 9001
      MOVIES_PATH: "/storage/media/movies"
      SHOWS_PATH: "/storage/media/shows"
      MISC_PATH: "/storage/torrent"
      MOVIES_CATEGORY: "Фильм"
      SHOWS_CATEGORY: "Сериал"
      MISC_CATEGORY: "Прочее"
      QBITTORRENT_USERNAME: "admin"
      QBITTORRENT_PASSWORD: "admin"
      REFRESH_INTERVAL: "3600"
      RETRY_INTERVAL: "300"
      CLEANUP_INTERVAL: "86400"
      LOG_LEVEL: "INFO"
    volumes:
      - /storage/media:/storage/media
      - /storage/torrent:/storage/torrent
```

> **Important**: The `volumes` section must mount the same paths that are used in `MOVIES_PATH`, `SHOWS_PATH`, and `MISC_PATH`. Otherwise, the script won't be able to access the filesystem for file operations and empty directory cleanup.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | — | Timezone for logs (e.g. `Europe/Moscow`) |
| `QBITTORRENT_HOST` | `http://localhost:8088` | qBittorrent Web UI URL |
| `QBITTORRENT_PORT` | `8080` | qBittorrent port |
| `QBITTORRENT_USERNAME` | `admin` | qBittorrent username |
| `QBITTORRENT_PASSWORD` | `adminadmin` | qBittorrent password |
| `MOVIES_PATH` | `/downloads/movies` | Destination path for movies |
| `SHOWS_PATH` | `/downloads/shows` | Base destination path for TV shows |
| `MISC_PATH` | `/downloads/data` | Destination path for misc content |
| `MOVIES_CATEGORY` | `Фильм` | Category name for movies |
| `SHOWS_CATEGORY` | `Сериал` | Category name for TV shows |
| `MISC_CATEGORY` | `Прочее` | Category name for misc content |
| `REFRESH_INTERVAL` | `3600` | Torrent check interval (seconds) |
| `RETRY_INTERVAL` | `300` | Retry interval on error (seconds) |
| `CLEANUP_INTERVAL` | `86400` | Empty directory cleanup interval (seconds, default 24h) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Show Name Extraction

For single-season TV shows, the script extracts the show name to create subfolders like `SHOWS_PATH/<Show Name>`. The name is taken from:

1. **Tag `Name: <Show Name>`** — if you set this tag in qBittorrent, it will be used as the folder name
2. **Torrent name** — if no tag is set, the script cleans the torrent name from quality/resolution/season info (e.g. `Breaking.Bad.S01.1080p.WEB-DL` → `Breaking Bad`)

Multi-season torrents (containing files from multiple seasons) are kept in `SHOWS_PATH` without subfolders.

Supported Architectures:

    AMD64 ✅
    ARM64 ✅
    ARMv7 ✅

## CI/CD – Docker image publishing

The repository contains a GitHub Actions workflow that builds and pushes a Docker image to the GitHub Container Registry.

### Triggers

* **`test` branch** – on every push the image is built and pushed with the tag `latest`. This provides an always‑up‑to‑date image for development/testing.
* **`release` branch** – on pushes (or on tags) the image is built and pushed with version tags that match the pattern `v*.*.*`. The workflow uses the `docker/metadata-action` to generate tags such as `v1.2.3` and `v1.2`.

### How it works

* The `flavor` option in the metadata step sets `latest` to `false` for the `test` branch and `true` for all other refs. This prevents the `latest` tag from being added automatically when we are already tagging the image explicitly.
* In the **Build and push Docker image** step the `tags` input selects `latest` for the `test` branch and the automatically generated tags for release builds:
  ```yaml
  tags: ${{ github.ref == 'refs/heads/test' && 'latest' || steps.meta.outputs.tags }}
  ```

You can trigger a release build by creating a tag like `v1.0.0` on the `release` branch.

For more details see the workflow file at [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml:1).
