# qBittorrent-sorter

## Overview

The qBittorrent-sorter is a simple script that sorts your torrents by type, such as movies, TV series, and general data. This sorting feature is particularly useful for users of media server applications like `Jellyfin`. 

## Usage 

docker-compose:

```yml
services:
  qBittorrent-sorter:
    build: .
    environment:
      QBITTORRENT_HOST: "http://192.168.0.100"
      QBITTORRENT_PORT: 9001
      MOVIES_PATH: "/downloads/movies"
      SHOWS_PATH: "/downloads/shows"
      MISC_PATH: "/downloads/data"
      QBITTORRENT_USERNAME: "admin"
      QBITTORRENT_PASSWORD: "admin"
      REFRESH_INTERVAL: "60"
      RETRY_INTERVAL: "60"
      LOG_LEVEL: "INFO"
```

Supported Architectures:

    AMD64 ✅
    ARM64 ✅
    ARMv7 ✅
