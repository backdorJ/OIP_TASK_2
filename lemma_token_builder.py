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
6) Пишет tokens.txt и lemmas.txt
"""

import os
import glob
import re
from html.parser import HTMLParser

import pymorphy2
import pymorphy2_dicts_ru

PAGES_DIR = "pages"
TOKENS_OUT = "tokens.txt"
LEMMAS_OUT = "lemmas.txt"

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
    # Приводим к нижнему регистру
    text = text.lower()

    # Берём только слова из русских букв
    tokens = RE_RU_WORD.findall(text)

    # Мини-фильтр от мусора: очень длинные "слова" часто бывают мусором
    tokens = [t for t in tokens if 2 <= len(t) <= 40]
    return tokens


def main():
    if not os.path.isdir(PAGES_DIR):
        raise FileNotFoundError(f"Нет папки {PAGES_DIR}/ (сначала запустите краулер)")

    dict_path = pymorphy2_dicts_ru.get_path()
    morph = pymorphy2.MorphAnalyzer(path=dict_path)

    # 1) Собираем все токены из всех файлов
    all_tokens = []
    files = sorted(glob.glob(os.path.join(PAGES_DIR, "*.txt")))
    if not files:
        raise FileNotFoundError(f"В {PAGES_DIR}/ нет *.txt файлов")

    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        text = html_to_text(html)
        all_tokens.extend(tokenize(text))

    # 2) убираем служебные части речи (союзы, предлоги, частицы и т.д.)
    # PREP (предлог), CONJ (союз), PRCL (частица), INTJ (междометие)
    bad_pos = {"PREP", "CONJ", "PRCL", "INTJ"}

    tokens_set: set[str] = set()
    lemma_to_tokens: dict[str, set[str]] = {}

    for tok in all_tokens:
        # убрать слова, содержащие цифры
        if any(ch.isdigit() for ch in tok):
            continue

        # анализ
        parses = morph.parse(tok)
        if not parses:
            continue
        p = parses[0]
        pos = p.tag.POS  # часть речи
        lemma = p.normal_form

        # не берём служебные слова
        if pos in bad_pos:
            continue

        # доп. защита от "мусора": лемма должна быть русской и адекватной длины
        if not RE_RU_WORD.fullmatch(lemma) or not (2 <= len(lemma) <= 40):
            continue

        tokens_set.add(tok)

        if lemma not in lemma_to_tokens:
            lemma_to_tokens[lemma] = set()
        lemma_to_tokens[lemma].add(tok)

    # Запись tokens.txt
    tokens_list = sorted(tokens_set)
    with open(TOKENS_OUT, "w", encoding="utf-8") as f:
        for t in tokens_list:
            f.write(t + "\n")

    # Запись lemmas.txt
    with open(LEMMAS_OUT, "w", encoding="utf-8") as f:
        for lemma in sorted(lemma_to_tokens.keys()):
            toks = sorted(lemma_to_tokens[lemma])
            f.write(lemma + " " + " ".join(toks) + "\n")

    print("Готово!")
    print(f"- Уникальных токенов: {len(tokens_list)} -> {TOKENS_OUT}")
    print(f"- Лемм: {len(lemma_to_tokens)} -> {LEMMAS_OUT}")


if __name__ == "__main__":
    main()
