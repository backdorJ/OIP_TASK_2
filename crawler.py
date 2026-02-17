#!/usr/bin/env python3
"""
Краулер: скачивает текстовые страницы из списка URL.
- Каждая страница сохраняется в текстовый файл вместе с HTML-разметкой.
- Создаётся index.txt: номер файла и ссылка на страницу.
"""
import os
import time
import urllib.error
import urllib.parse
import urllib.request

PAGES_DIR = "pages"
URLS_FILE = "urls.txt"
INDEX_FILE = "index.txt"
MIN_PAGES = 100
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OIP_Crawler/1.0; educational task)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
REQUEST_TIMEOUT = 30
DELAY_BETWEEN_REQUESTS = 0.5


def load_urls(path: str) -> list[str]:
    """Загрузить список URL из файла (по одному на строку)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Файл {path} не найден. Сначала запустите: python get_url_list.py"
        )
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def safe_filename(index: int) -> str:
    """Имя файла для страницы: 1.txt, 2.txt, ..."""
    return f"{index}.txt"


def fetch_url(url: str) -> tuple[str, str, str] | None:
    """
    Скачать URL. Возвращает (body, final_url, content_type) или None при ошибке.
    """
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
            return (body, final_url, content_type)
    except (urllib.error.URLError, OSError) as e:
        return None


def run():
    os.makedirs(PAGES_DIR, exist_ok=True)
    urls = load_urls(URLS_FILE)
    index_entries = []
    file_index = 0
    saved = 0

    for i, url in enumerate(urls, start=1):

        if saved >= MIN_PAGES:
            break

        result = fetch_url(url)

        if result is None:
            print(f"[{i}] Ошибка загрузки: {url}")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        body, final_url, content_type = result
        file_index += 1
        path = os.path.join(PAGES_DIR, safe_filename(file_index))

        # сюда по path записываем html
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write(body)

        # сохраняем индекс файла и ссылку страницы
        index_entries.append((file_index, url))
        saved += 1
        print(f"[{saved}] Сохранено: {file_index}.txt — {url[:60]}...")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        for num, link in index_entries:
            f.write(f"{num}\t{link}\n")

    print(f"\nГотово. Сохранено страниц: {saved}. Index: {INDEX_FILE}, файлы в {PAGES_DIR}/")

if __name__ == "__main__":
    run()