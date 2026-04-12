import os
import re
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
MOVIES_PATH = os.getenv('MOVIES_PATH', '/downloads/movies')
SHOWS_PATH = os.getenv('SHOWS_PATH', '/downloads/shows')
MISC_PATH = os.getenv('MISC_PATH', '/downloads/data')
MOVIES_CATEGORY = os.getenv('MOVIES_CATEGORY', 'Фильм')
SHOWS_CATEGORY = os.getenv('SHOWS_CATEGORY', 'Сериал')
MISC_CATEGORY = os.getenv('MISC_CATEGORY', 'Прочее')
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', 3600))
RETRY_INTERVAL = int(os.getenv('RETRY_INTERVAL', 300))
CLEANUP_INTERVAL = int(os.getenv('CLEANUP_INTERVAL', 86400))


def main_loop(logger):
    last_cleanup = time.time()
    while True:
        try:
            qbt_client = qbittorrentapi.Client(
                host=QBITTORRENT_HOST,
                port=QBITTORRENT_PORT,
                username=QBITTORRENT_USERNAME,
                password=QBITTORRENT_PASSWORD
            )
            qbt_client.auth_log_in()

            # Очистка при запуске
            logger.info('Starting empty directory cleanup...')
            cleanup_all_empty_dirs([MOVIES_PATH, SHOWS_PATH, MISC_PATH], logger)
            last_cleanup = time.time()

            while True:
                # Обработка торрентов
                torrents = qbt_client.torrents_info()
                for torrent in torrents:
                    process_torrent(qbt_client, torrent, logger)

                # Очистка пустых папок по расписанию
                now = time.time()
                if now - last_cleanup >= CLEANUP_INTERVAL:
                    cleanup_all_empty_dirs([MOVIES_PATH, SHOWS_PATH, MISC_PATH], logger)
                    last_cleanup = now

                time.sleep(REFRESH_INTERVAL)

        except qbittorrentapi.LoginFailed as e:
            logger.error(f"Login error: {e}")
            time.sleep(RETRY_INTERVAL)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(RETRY_INTERVAL)


def extract_show_name(torrent, logger):
    """Извлекает название сериала из тега вида 'Name: {Название сериала}' или имени торрента."""
    # Получаем теги — могут быть строкой или списком
    tags_raw = getattr(torrent, 'tags', None)
    if tags_raw:
        if isinstance(tags_raw, str):
            tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]
        elif isinstance(tags_raw, list):
            tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
        else:
            tags = []

        for tag in tags:
            logger.debug(f'Checking tag: "{tag}" for torrent "{torrent.name}"')
            if tag.startswith('Name:'):
                show_name = tag[len('Name:'):].strip()
                logger.debug(f'Found show name "{show_name}" in tag for torrent "{torrent.name}"')
                return show_name

    # Если тега с именем нет, извлекаем из имени торрента
    name = torrent.name
    # Убираем информацию о сезоне/эпизоде, качестве, разрешении и т.д.
    # Сначала убираем паттерны с точками и дефисами как разделителями
    name = re.sub(r'[.\s_-]+([Ss]\d+[Ee]?\d*|\d+[xX]\d+|WEB[-_ ]?[Dd][Ll]|WEBRip|HDTV|Blu[-_ ]?[Rr]ay|BDRip|HDRip|XviD|x264|x265|HEVC|AAC|AC3|DD5\.1|DTS|[Rr]us|[Ee]ng|[Uu]kr|SUB|NVO|TV)', '', name, flags=re.IGNORECASE)
    # Убираем разрешение (1080p, 720p, 2160p, 4K и т.д.)
    name = re.sub(r'[.\s_-]+(\d{3,4}[pP]|4[Kk])', '', name, flags=re.IGNORECASE)
    # Убираем год
    name = re.sub(r'[.\s_-]+(\d{4})', '', name, flags=re.IGNORECASE)
    # Заменяем точки и подчёркивания на пробелы
    name = re.sub(r'[._-]+', ' ', name).strip()
    # Убираем лишние пробелы и скобки
    name = name.strip('[]{}() ')

    return name if name else torrent.name


def has_multiple_seasons(torrent, client):
    """Проверяет, содержит ли торрент файлы нескольких сезонов."""
    seasons = set()
    for file in client.torrents_files(torrent.hash):
        match = re.search(r'[Ss](\d+)', file.name)
        if match:
            seasons.add(int(match.group(1)))
        else:
            # Проверяем паттерн "Season X" или "Сезон X"
            match = re.search(r'[Ss]eason\s*(\d+)|[Сс]езон\s*(\d+)', file.name, re.IGNORECASE)
            if match:
                season_num = int(match.group(1) or match.group(2))
                seasons.add(season_num)
    return len(seasons) > 1


def set_category(client, torrent, category, logger):
    """Устанавливает категорию для торрента."""
    if torrent.category != category:
        try:
            client.torrents_setCategory(torrent_hashes=torrent.hash, category=category)
            logger.info(f'Torrent "{torrent.name}" assigned to category "{category}"')
        except Exception as e:
            logger.error(f'Error setting category for torrent "{torrent.name}": {e}')


def normalize_path(path):
    """Нормализует путь для сравнения."""
    return os.path.normpath(path).rstrip(os.sep).lower()


def cleanup_all_empty_dirs(base_paths, logger):
    """Рекурсивно обходит все указанные пути и удаляет пустые папки (снизу вверх)."""
    cleaned = 0
    for base_path in base_paths:
        base_path = os.path.normpath(base_path)
        if not os.path.isdir(base_path):
            logger.debug(f'Path does not exist, skipping: {base_path}')
            continue
        # Собираем все подпапки, сортируем по глубине (сначала глубокие)
        dirs = []
        for root, subdirs, _ in os.walk(base_path):
            for d in subdirs:
                dirs.append(os.path.join(root, d))
        dirs.sort(key=lambda p: p.count(os.sep), reverse=True)
        logger.debug(f'Found {len(dirs)} subdirectories in {base_path}')
        # Удаляем пустые снизу вверх
        for d in dirs:
            if os.path.isdir(d) and not os.listdir(d):
                try:
                    os.rmdir(d)
                    logger.info(f'Removed empty directory: {d}')
                    cleaned += 1
                except OSError:
                    pass
    if cleaned:
        logger.info(f'Cleanup done: {cleaned} empty director{"y" if cleaned == 1 else "ies"} removed.')
    else:
        logger.debug('No empty directories found during cleanup.')
    return cleaned


def process_torrent(client, torrent, logger):
    media_count = sum(
        file.name.endswith(('.mp4', '.mkv', '.avi', '.mov', '.m4v')) for file in client.torrents_files(torrent.hash))
    destination_folder = MISC_PATH
    category = MISC_CATEGORY

    if media_count == 1:
        destination_folder = MOVIES_PATH
        category = MOVIES_CATEGORY
    elif media_count > 1:
        category = SHOWS_CATEGORY
        # Если торрент содержит несколько сезонов — не перемещаем в папку с названием
        if not has_multiple_seasons(torrent, client):
            show_name = extract_show_name(torrent, logger)
            destination_folder = os.path.join(SHOWS_PATH, show_name)
            logger.debug(f'Show name extracted: "{show_name}"')
        else:
            destination_folder = SHOWS_PATH

    # Устанавливаем категорию
    set_category(client, torrent, category, logger)

    # Перемещаем только если торрент не на своём месте
    if normalize_path(torrent.save_path) != normalize_path(destination_folder):
        try:
            # Отключаем автоматическое управление, иначе setLocation может игнорироваться
            if torrent.auto_tmm:
                client.torrents_set_auto_management(enable=False, torrent_hashes=torrent.hash)
                logger.debug(f'Disabled auto management for "{torrent.name}"')

            client.torrents_setLocation(torrent_hashes=torrent.hash, location=destination_folder)
            logger.info(f'Torrent "{torrent.name}" moved to {destination_folder}')
        except Exception as e:
            logger.error(f'Error moving torrent "{torrent.name}": {e}')


if __name__ == "__main__":
    logger = setup_logging()
    main_loop(logger)
