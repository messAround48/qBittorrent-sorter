import os
import time
import logging
import qbittorrentapi


def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger()


QBITTORRENT_HOST = os.getenv('QBITTORRENT_HOST', 'http://localhost:8088')
QBITTORRENT_PORT = os.getenv('QBITTORRENT_PORT', 8080)
QBITTORRENT_USERNAME = os.getenv('QBITTORRENT_USERNAME', 'admin')
QBITTORRENT_PASSWORD = os.getenv('QBITTORRENT_PASSWORD', 'adminadmin')
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', 3600))
RETRY_INTERVAL = int(os.getenv('RETRY_INTERVAL', 300))


def main_loop(logger):
    while True:
        try:
            qbt_client = qbittorrentapi.Client(
                host=QBITTORRENT_HOST,
                port=QBITTORRENT_PORT,
                username=QBITTORRENT_USERNAME,
                password=QBITTORRENT_PASSWORD
            )
            qbt_client.auth_log_in()

            while True:
                # Обработка торрентов
                torrents = qbt_client.torrents_info()
                for torrent in torrents:
                    process_torrent(qbt_client, torrent, logger)
                time.sleep(REFRESH_INTERVAL)

        except qbittorrentapi.LoginFailed as e:
            logger.error(f"Login error: {e}")
            time.sleep(RETRY_INTERVAL)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(RETRY_INTERVAL)


def process_torrent(client, torrent, logger):
    media_count = sum(
        file.name.endswith(('.mp4', '.mkv', '.avi', '.mov', '.m4v')) for file in client.torrents_files(torrent.hash))
    destination_folder = '/downloads/data'
    if media_count == 1:
        destination_folder = '/downloads/films'
    elif media_count > 1:
        destination_folder = '/downloads/serials'

    if torrent.save_path.rstrip('/') != destination_folder:
        try:
            client.torrents_setLocation(torrent_hashes=torrent.hash, location=destination_folder)
            logger.info(f'Torrent "{torrent.name}" moved to folder {destination_folder}.')
        except Exception as e:
            logger.error(f'Error moving torrent "{torrent.name}": {e}')


if __name__ == "__main__":
    logger = setup_logging()
    main_loop(logger)
