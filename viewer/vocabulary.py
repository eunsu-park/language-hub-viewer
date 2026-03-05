"""Vocabulary YAML loading and filtering."""
from functools import lru_cache
from pathlib import Path

import yaml

from config import Config, CONTENT_DIR


def _vocab_dir(course: str) -> Path:
    """Return the vocabulary directory for a course."""
    return CONTENT_DIR / course / "vocabulary"


def _load_yaml(path: Path) -> dict:
    """Load a single YAML file, returning empty dict on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def load_vocabulary(course: str) -> list[dict]:
    """Load all vocabulary YAML files for a course.

    Each file is expected to be named ``{nn}_{topic}.yaml`` and contain
    keys such as ``lesson``, ``lesson_number``, ``cefr``, and
    ``categories`` (a list of word groups).

    Returns a list of lesson vocabulary dicts sorted by lesson number.
    Results are cached (backed by *_load_vocabulary_cached*).
    """
    vdir = _vocab_dir(course)
    if not vdir.exists():
        return []
    mtime = vdir.stat().st_mtime
    return list(_load_vocabulary_cached(course, mtime))


@lru_cache(maxsize=64)
def _load_vocabulary_cached(course: str, _dir_mtime: float) -> tuple[dict, ...]:
    """Cached inner loader; *_dir_mtime* busts the cache on changes."""
    vdir = _vocab_dir(course)
    lessons: list[dict] = []
    for yaml_path in sorted(vdir.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        data = _load_yaml(yaml_path)
        if data:
            lessons.append(data)
    return tuple(lessons)


def get_vocabulary_by_lesson(course: str, lesson_number: int) -> dict:
    """Get vocabulary for a specific lesson number.

    Returns the matching lesson dict, or an empty dict if not found.
    """
    for lesson in load_vocabulary(course):
        if lesson.get("lesson_number") == lesson_number:
            return lesson
    return {}


def get_vocabulary_by_cefr(course: str, cefr: str) -> list[dict]:
    """Filter vocabulary lessons by CEFR level (e.g. ``"A1"``, ``"B2"``)."""
    cefr_upper = cefr.upper()
    return [
        lesson for lesson in load_vocabulary(course)
        if lesson.get("cefr", "").upper() == cefr_upper
    ]


def _resolve_i18n(value, lang: str) -> str:
    """Extract a localized string from a dict or return as-is."""
    if isinstance(value, dict):
        return value.get(lang, value.get("en", ""))
    return value or ""


def get_all_words(course: str, lang: str | None = None) -> list[dict]:
    """Flatten all categories from all lessons into a single word list.

    Each returned dict contains the word data (``target``, ``translation``,
    ``gender``, ``notes``) plus context keys: ``lesson``, ``lesson_number``,
    ``cefr``, and ``category``.

    The target-language word is read from a dynamic YAML key derived from the
    course name (e.g. ``spanish`` for Spanish, ``german`` for German).  A
    ``"target"`` fallback key is also tried so that future YAML files can use
    a generic field name.

    When *lang* is provided, bilingual fields (translation, notes, category
    label) are resolved to the matching language string.
    """
    if lang is None:
        lang = Config.DEFAULT_LANGUAGE

    word_key = course.lower()  # "Spanish" -> "spanish", "German" -> "german"

    words: list[dict] = []
    for lesson in load_vocabulary(course):
        lesson_name = lesson.get("lesson", "")
        lesson_num = lesson.get("lesson_number", 0)
        cefr = lesson.get("cefr", "")
        for cat in lesson.get("categories", []):
            cat_id = cat.get("id", "")
            cat_label = _resolve_i18n(cat.get("label", ""), lang)
            for word in cat.get("words", []):
                target = word.get(word_key, word.get("target", ""))
                translation = _resolve_i18n(word.get("translation", ""), lang)
                notes = _resolve_i18n(word.get("notes", ""), lang)
                gender = word.get("gender") or ""
                words.append({
                    "lesson": lesson_name,
                    "lesson_number": lesson_num,
                    "cefr": cefr,
                    "category": cat_id,
                    "category_label": cat_label,
                    "target": target,
                    "translation": translation,
                    "gender": gender,
                    "notes": notes,
                    "word_key": f"{lesson_num}:{cat_id}:{target}",
                })
    return words


def get_word_count(course: str) -> int:
    """Total word count across all vocabulary lessons for a course."""
    return len(get_all_words(course))
