"""docstring"""
import os
import re
import time
import logging

import qbittorrentapi

QBITTORRENT_HOST = os.getenv('QBITTORRENT_HOST', 'http://localhost:8088')
QBITTORRENT_PORT = os.getenv('QBITTORRENT_PORT', '8080')
QBITTORRENT_USERNAME = os.getenv('QBITTORRENT_USERNAME', 'admin')
QBITTORRENT_PASSWORD = os.getenv('QBITTORRENT_PASSWORD', 'adminadmin')
MOVIES_PATH = os.getenv('MOVIES_PATH', '/downloads/movies')
SHOWS_PATH = os.getenv('SHOWS_PATH', '/downloads/shows')
MISC_PATH = os.getenv('MISC_PATH', '/downloads/data')
MOVIES_CATEGORY = os.getenv('MOVIES_CATEGORY', 'Фильм')
SHOWS_CATEGORY = os.getenv('SHOWS_CATEGORY', 'Сериал')
MISC_CATEGORY = os.getenv('MISC_CATEGORY', 'Прочее')
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', '3600'))
RETRY_INTERVAL = int(os.getenv('RETRY_INTERVAL', '300'))
CLEANUP_INTERVAL = int(os.getenv('CLEANUP_INTERVAL', '86400'))
LOG_LEVEL = getattr(logging, os.getenv('LOG_LEVEL', 'DEBUG').upper(), 'INFO')
LOG_FORMATTER = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

log_stream_handler = logging.StreamHandler()
log_stream_handler.setFormatter(LOG_FORMATTER)
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_stream_handler)
logger.debug('Logger inititated. Level: %s', logging.getLevelName(logger.getEffectiveLevel()))

qbt_client = qbittorrentapi.Client(
    host=QBITTORRENT_HOST,
    port=QBITTORRENT_PORT,
    username=QBITTORRENT_USERNAME,
    password=QBITTORRENT_PASSWORD
)
logger.debug(
    'QBT Client configured. Host: %s:%s, username: %s',
    qbt_client.host,
    qbt_client.port,
    qbt_client.username
)

logger.debug('Movies path: %s', MOVIES_PATH)
logger.debug('Shows path: %s', SHOWS_PATH)
logger.debug('Misc path: %s', MISC_PATH)
logger.debug('Movies category: %s', MOVIES_CATEGORY)
logger.debug('Shows category: %s', SHOWS_CATEGORY)
logger.debug('Misc category: %s', MISC_CATEGORY)
logger.debug('Refresh interval: %s seconds', REFRESH_INTERVAL)
logger.debug('Retry interval: %s seconds', RETRY_INTERVAL)
logger.debug('Cleanup interval: %s seconds', CLEANUP_INTERVAL)



def extract_show_name(input_torrent, input_logger):
    """Извлекает название сериала из тега вида 'Name: {Название сериала}' или имени торрента."""
    # Получаем теги — могут быть строкой или списком
    tags_raw = getattr(input_torrent, 'tags', None)
    if tags_raw:
        if isinstance(tags_raw, str):
            tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]
        elif isinstance(tags_raw, list):
            tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
        else:
            tags = []

        for tag in tags:
            input_logger.debug(f'Checking tag: "{tag}" for torrent "{input_torrent.name}"')
            if tag.startswith('Name:'):
                show_name = tag[len('Name:'):].strip()
                input_logger.debug(f'Found show name "{show_name}" \
                 in tag for torrent "{input_torrent.name}"')
                return show_name

    # Если тега с именем нет, извлекаем из имени торрента
    name = input_torrent.name
    # Убираем информацию о сезоне/эпизоде, качестве, разрешении и т.д.
    # Сначала убираем паттерны с точками и дефисами как разделителями
    name = re.sub(
        r'[.\s_-]+([Ss]\d+[Ee]?\d*|\d+[xX]\d+ \\'
        r'|WEB[-_ ]?[Dd][Ll]|WEBRip|HDTV|Blu[-_ ]? \\'
        r'[Rr]ay|BDRip|HDRip|XviD|x264|x265|HEVC|AAC \\'
        r'|AC3|DD5\.1|DTS|[Rr]us|[Ee]ng|[Uu]kr|SUB|NVO|TV)',
        '', name, flags=re.IGNORECASE)
    # Убираем разрешение (1080p, 720p, 2160p, 4K и т.д.)
    name = re.sub(r'[.\s_-]+(\d{3,4}[pP]|4[Kk])', '', name, flags=re.IGNORECASE)
    # Убираем год
    name = re.sub(r'[.\s_-]+(\d{4})', '', name, flags=re.IGNORECASE)
    # Заменяем точки и подчёркивания на пробелы
    name = re.sub(r'[._-]+', ' ', name).strip()
    # Убираем лишние пробелы и скобки
    name = name.strip('[]{}() ')

    return name if name else input_torrent.name


def has_multiple_seasons(input_torrent, client):
    """Проверяет, содержит ли торрент файлы нескольких сезонов."""
    seasons = set()
    for file in client.torrents_files(input_torrent.hash):
        match = re.search(r'[Ss](\d+)', file.name)
        if match:
            seasons.add(int(match.group(1)))
        else:
            # Проверяем паттерн "Season*X" или "Сезон*X"
            match = re.search(r'[Ss]eason(?:\s*|_+)(\d+)|[Сс]езон(?:\s*|_+)(\d+)',
                              file.name,
                              re.IGNORECASE)
            if match:
                season_num = int(match.group(1) or match.group(2))
                seasons.add(season_num)
    return len(seasons) > 1


def set_category(client, input_torrent, category, input_logger):
    """Устанавливает категорию для торрента."""
    if input_torrent.category != category:
        try:
            client.torrents_setCategory(torrent_hashes=input_torrent.hash, category=category)
            input_logger.info(f'Torrent "{input_torrent.name}" assigned to category "{category}"')
        except qbittorrentapi.APIError as e:
            input_logger.error(f'Error setting category for torrent "{input_torrent.name}": {e}')


def normalize_path(path):
    """Нормализует путь для сравнения."""
    return os.path.normpath(path).rstrip(os.sep).lower()


def cleanup_all_empty_dirs(base_paths, input_logger):
    """Рекурсивно обходит все указанные пути и удаляет пустые папки (снизу вверх)."""
    cleaned = 0
    for base_path in base_paths:
        base_path = os.path.normpath(base_path)
        if not os.path.isdir(base_path):
            input_logger.debug(f'Path does not exist, skipping: {base_path}')
            continue
        # Собираем все подпапки, сортируем по глубине (сначала глубокие)
        dirs = []
        for root, subdirs, _ in os.walk(base_path):
            for d in subdirs:
                dirs.append(os.path.join(root, d))
        dirs.sort(key=lambda p: p.count(os.sep), reverse=True)
        input_logger.debug(f'Found {len(dirs)} subdirectories in {base_path}')
        # Удаляем пустые снизу вверх
        for d in dirs:
            if os.path.isdir(d) and not os.listdir(d):
                try:
                    os.rmdir(d)
                    input_logger.info(f'Removed empty directory: {d}')
                    cleaned += 1
                except OSError:
                    pass
    if cleaned:
        input_logger.debug('Cleanup done: %s empty director%s removed.',
                           cleaned,
                     "y" if cleaned == 1 else "ies")
    else:
        input_logger.debug('No empty directories found during cleanup.')
    return cleaned

def check_for_missing_files(input_torrent):
    """Проверка на ошибку 'Отсутствуют файлы'"""
    return input_torrent.info.get('state') == 'missingFiles'

def process_torrent(client, input_torrent, input_logger):
    """Основная функция обработки торрентов.
    Удаляет торренты, в которых state = missingFiles (файлы были удалены).
    Затем считает количество медиафайлов и распределяет по категориям.
    После этого происходит перемещение торрентов.
    """
    if check_for_missing_files(torrent):
        input_logger.info(
            'Deleting torrent %s due to state = "missingFiles"',
            torrent.info.get('name')
        )
        torrent.delete()
    media_count = sum(
        file.name.endswith(
            ('.mp4', '.mkv', '.avi', '.mov', '.m4v')) \
            for file in client.torrents_files(input_torrent.hash)
    )
    destination_folder = MISC_PATH
    category = MISC_CATEGORY

    if media_count == 1:
        destination_folder = MOVIES_PATH
        category = MOVIES_CATEGORY
    elif media_count > 1:
        category = SHOWS_CATEGORY
        # Если торрент содержит несколько сезонов — не перемещаем в папку с названием
        if not has_multiple_seasons(input_torrent, client):
            show_name = extract_show_name(input_torrent, input_logger)
            destination_folder = os.path.join(SHOWS_PATH, show_name)
            input_logger.debug(f'Show name extracted: "{show_name}"')
        else:
            destination_folder = SHOWS_PATH

    # Устанавливаем категорию
    set_category(client, input_torrent, category, input_logger)

    # Перемещаем только если торрент не на своём месте
    if normalize_path(input_torrent.save_path) != normalize_path(destination_folder):
        try:
            # Отключаем автоматическое управление, иначе setLocation может игнорироваться
            if input_torrent.auto_tmm:
                client.torrents_set_auto_management(enable=False, torrent_hashes=input_torrent.hash)
                input_logger.debug(f'Disabled auto management for "{input_torrent.name}"')
            client.torrents_setLocation(
                torrent_hashes=input_torrent.hash,
                location=destination_folder
            )
            input_logger.info(f'Torrent "{input_torrent.name}" \
             moved to {destination_folder}')
        except qbittorrentapi.APIError as e:
            input_logger.error(f'Error moving torrent "{input_torrent.name}": {e}')


last_cleanup = time.time()
while True:
    try:
        qbt_client.auth_log_in()
        # Очистка при запуске
        logger.info('Starting empty directory cleanup...')
        cleanup_all_empty_dirs([MOVIES_PATH, SHOWS_PATH, MISC_PATH], logger)
        # Обработка торрентов
        torrents = qbt_client.torrents_info()
        for torrent in torrents:
            process_torrent(qbt_client, torrent, logger)
        # Очистка пустых папок по расписанию
        now = time.time()
        if now - last_cleanup >= CLEANUP_INTERVAL:
            cleanup_all_empty_dirs([MOVIES_PATH, SHOWS_PATH, MISC_PATH], logger)
            last_cleanup = now
        qbt_client.auth_log_out()
        time.sleep(REFRESH_INTERVAL)
    except qbittorrentapi.LoginFailed as e:
        logger.error("Login error: %s", e)
        time.sleep(RETRY_INTERVAL)
    except qbittorrentapi.APIError as e:
        logger.error("Error: %s", e)
        time.sleep(RETRY_INTERVAL)
