"""Grammar YAML loading and drill data generation."""
import random
from functools import lru_cache
from pathlib import Path

import yaml

from config import Config, CONTENT_DIR


def _grammar_dir(course: str) -> Path:
    """Return the grammar directory for a course."""
    return CONTENT_DIR / course / "grammar"


def _load_yaml(path: Path) -> dict:
    """Load a single YAML file, returning empty dict on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _resolve_i18n(value, lang: str) -> str:
    """Extract a localized string from a dict or return as-is."""
    if isinstance(value, dict):
        return value.get(lang, value.get("en", ""))
    return value or ""


# ---------------------------------------------------------------------------
# Raw loaders (with mtime-based LRU cache)
# ---------------------------------------------------------------------------

def load_conjugations(course: str) -> dict:
    """Return the full conjugations dict with verb paradigms."""
    gdir = _grammar_dir(course)
    if not gdir.exists():
        return {}
    mtime = gdir.stat().st_mtime
    return dict(_load_conjugations_cached(course, mtime))


@lru_cache(maxsize=64)
def _load_conjugations_cached(course: str, _dir_mtime: float) -> dict:
    """Cached inner loader for conjugations.yaml."""
    path = _grammar_dir(course) / "conjugations.yaml"
    return _load_yaml(path)


def load_tense_rules(course: str) -> dict:
    """Return tense rules."""
    gdir = _grammar_dir(course)
    if not gdir.exists():
        return {}
    mtime = gdir.stat().st_mtime
    return dict(_load_tense_rules_cached(course, mtime))


@lru_cache(maxsize=64)
def _load_tense_rules_cached(course: str, _dir_mtime: float) -> dict:
    """Cached inner loader for tense_rules.yaml."""
    path = _grammar_dir(course) / "tense_rules.yaml"
    return _load_yaml(path)


def load_grammar_rules(course: str) -> dict:
    """Return grammar rules."""
    gdir = _grammar_dir(course)
    if not gdir.exists():
        return {}
    mtime = gdir.stat().st_mtime
    return dict(_load_grammar_rules_cached(course, mtime))


@lru_cache(maxsize=64)
def _load_grammar_rules_cached(course: str, _dir_mtime: float) -> dict:
    """Cached inner loader for grammar_rules.yaml."""
    path = _grammar_dir(course) / "grammar_rules.yaml"
    return _load_yaml(path)


# ---------------------------------------------------------------------------
# Verb helpers
# ---------------------------------------------------------------------------

def get_verb(course: str, verb: str) -> dict | None:
    """Get conjugation data for a specific verb."""
    data = load_conjugations(course)
    verbs = data.get("verbs", {})
    return verbs.get(verb)


def get_verb_list(course: str) -> list[dict]:
    """Return list of {infinitive, type, group, meaning} for all verbs."""
    data = load_conjugations(course)
    verbs = data.get("verbs", {})
    result: list[dict] = []
    for key, info in verbs.items():
        result.append({
            "infinitive": info.get("infinitive", key),
            "type": info.get("type", ""),
            "group": info.get("group", ""),
            "meaning": info.get("meaning", {}),
        })
    return result


# ---------------------------------------------------------------------------
# Tense helpers
# ---------------------------------------------------------------------------

def get_tense(course: str, tense: str) -> dict | None:
    """Get a specific tense's rules."""
    data = load_tense_rules(course)
    tenses = data.get("tenses", {})
    return tenses.get(tense)


def get_tense_list(course: str) -> list[dict]:
    """Return list of tense summaries."""
    data = load_tense_rules(course)
    tenses = data.get("tenses", {})
    result: list[dict] = []
    for key, info in tenses.items():
        result.append({
            "id": info.get("id", key),
            "label": info.get("label", {}),
            "formation": info.get("formation", {}),
        })
    return result


# ---------------------------------------------------------------------------
# Grammar rule helpers
# ---------------------------------------------------------------------------

def get_rule(course: str, rule_id: str) -> dict | None:
    """Get a specific grammar rule."""
    data = load_grammar_rules(course)
    rules = data.get("rules", {})
    return rules.get(rule_id)


def get_rule_list(course: str) -> list[dict]:
    """Return list of rule summaries."""
    data = load_grammar_rules(course)
    rules = data.get("rules", {})
    result: list[dict] = []
    for key, info in rules.items():
        result.append({
            "id": info.get("id", key),
            "label": info.get("label", {}),
            "category": info.get("category", ""),
            "cefr": info.get("cefr", info.get("jlpt", info.get("topik", info.get("hanja_level", "")))),
            "description": info.get("description", {}),
        })
    return result


# ---------------------------------------------------------------------------
# Conjugation drill
# ---------------------------------------------------------------------------

_PERSONS = ["yo", "tú", "él/ella/usted", "nosotros", "vosotros", "ellos/ellas/ustedes"]


def get_conjugation_drill_data(
    course: str,
    verb: str | None = None,
    tense: str | None = None,
) -> list[dict]:
    """Return a list of drill items for conjugation practice.

    Each item: ``{verb, tense, person, correct_answer, hint}``.
    If *verb* / *tense* are not specified, picks a random selection.
    Used by the conjugation practice feature.
    """
    data = load_conjugations(course)
    verbs = data.get("verbs", {})
    if not verbs:
        return []

    # Determine which verbs to drill
    if verb:
        selected_verbs = {verb: verbs[verb]} if verb in verbs else {}
    else:
        keys = list(verbs.keys())
        random.shuffle(keys)
        selected_verbs = {k: verbs[k] for k in keys[:5]}

    items: list[dict] = []
    for v_key, v_info in selected_verbs.items():
        tenses_data = v_info.get("tenses", {})
        infinitive = v_info.get("infinitive", v_key)
        group = v_info.get("group", "")
        meaning = v_info.get("meaning", {})

        # Determine which tenses to drill
        if tense:
            drill_tenses = {tense: tenses_data[tense]} if tense in tenses_data else {}
        else:
            t_keys = list(tenses_data.keys())
            random.shuffle(t_keys)
            drill_tenses = {k: tenses_data[k] for k in t_keys[:3]}

        for t_key, forms in drill_tenses.items():
            if not isinstance(forms, dict):
                continue
            for person, correct in forms.items():
                if not correct or not isinstance(correct, str):
                    continue
                items.append({
                    "verb": infinitive,
                    "group": group,
                    "meaning": meaning,
                    "tense": t_key,
                    "person": person,
                    "correct_answer": correct,
                    "hint": f"{group} {t_key}",
                })

    random.shuffle(items)
    return items
