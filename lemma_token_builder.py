#!/usr/bin/env python3

import inspect
if not hasattr(inspect, "getargspec"):
    def _getargspec(f):
        spec = inspect.getfullargspec(f)
        return (spec.args, spec.varargs, spec.varkw, spec.defaults)
    inspect.getargspec = _getargspec

"""
process_pages.py
1) Читает HTML из pages/*.txt
2) Чистит текст (убирает теги, script/style)
3) Токенизация (только русские слова)
4) Фильтрация:
   - без дубликатов
   - без чисел
   - без смешанных букв+цифр
   - без "служебных" частей речи: предлоги, союзы, частицы, междометия (по pymorphy2)
   - минимум мусора
5) Группировка по леммам
6) Для каждой страницы создаёт папку page1, page2, … с файлами tokens.txt и lemmas.txt
"""

import os
import glob
import re
from html.parser import HTMLParser

import pymorphy2
import pymorphy2_dicts_ru

PAGES_DIR = "pages"
OUTPUT_DIR = "tokenized_pages"

# Только русские слова (включая ё), длина >= 2
RE_RU_WORD = re.compile(r"[а-яё]{2,}", re.IGNORECASE)


class HTMLTextExtractor(HTMLParser):
    """Достаём только видимый текст из HTML, игнорируем script/style."""
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = 0  # внутри script/style

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("script", "style", "noscript") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0 and data:
            self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def html_to_text(html: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = RE_RU_WORD.findall(text)

    tokens = [t for t in tokens if 2 <= len(t) <= 40]
    return tokens


def process_page(html: str, morph, bad_pos: set) -> tuple[list[str], dict[str, set[str]]]:
    """Из HTML страницы извлекает токены и группу лемма->токены для этой страницы."""
    text = html_to_text(html)
    raw_tokens = tokenize(text)

    tokens_set: set[str] = set()
    lemma_to_tokens: dict[str, set[str]] = {}

    for tok in raw_tokens:
        if any(ch.isdigit() for ch in tok):
            continue
        parses = morph.parse(tok)
        if not parses:
            continue
        p = parses[0]
        pos = p.tag.POS
        lemma = p.normal_form
        if pos in bad_pos:
            continue
        if not RE_RU_WORD.fullmatch(lemma) or not (2 <= len(lemma) <= 40):
            continue

        tokens_set.add(tok)
        if lemma not in lemma_to_tokens:
            lemma_to_tokens[lemma] = set()
        lemma_to_tokens[lemma].add(tok)

    tokens_list = sorted(tokens_set)
    return tokens_list, lemma_to_tokens


def main():
    if not os.path.isdir(PAGES_DIR):
        raise FileNotFoundError(f"Нет папки {PAGES_DIR}/ (сначала запустите краулер)")

    dict_path = pymorphy2_dicts_ru.get_path()
    morph = pymorphy2.MorphAnalyzer(path=dict_path)
    bad_pos = {"PREP", "CONJ", "PRCL", "INTJ"}

    def page_number(path):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            return int(name)
        except ValueError:
            return 0

    files = sorted(glob.glob(os.path.join(PAGES_DIR, "*.txt")), key=page_number)
    if not files:
        raise FileNotFoundError(f"В {PAGES_DIR}/ нет *.txt файлов")

    for path in files:
        base = os.path.splitext(os.path.basename(path))[0]
        page_dir = os.path.join(OUTPUT_DIR, f"page{base}")
        os.makedirs(page_dir, exist_ok=True)

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()

        tokens_list, lemma_to_tokens = process_page(html, morph, bad_pos)

        with open(os.path.join(page_dir, "tokens.txt"), "w", encoding="utf-8") as f:
            for t in tokens_list:
                f.write(t + "\n")

        with open(os.path.join(page_dir, "lemmas.txt"), "w", encoding="utf-8") as f:
            for lemma in sorted(lemma_to_tokens.keys()):
                toks = sorted(lemma_to_tokens[lemma])
                f.write(lemma + " " + " ".join(toks) + "\n")

    print("Готово!")
    print(f"- Обработано страниц: {len(files)}")

if __name__ == "__main__":
    main()
