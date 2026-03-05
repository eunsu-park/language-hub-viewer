"""Quiz question generation from vocabulary and grammar YAML.

Supports four quiz types:
- vocab: multiple-choice (target word -> pick correct translation)
- fill_blank: type the target word given the translation
- conjugation: multiple-choice (verb+tense+person -> pick correct form)
- mixed: balanced mix of all three types
"""
import random
import unicodedata


def _normalize(text: str) -> str:
    """NFC-normalize and lowercase for accent-tolerant comparison."""
    return unicodedata.normalize("NFC", text.lower().strip())


def _pick_distractors(pool: list[str], correct: str, count: int = 3) -> list[str]:
    """Pick `count` unique wrong answers from pool, excluding `correct`."""
    candidates = [w for w in pool if _normalize(w) != _normalize(correct)]
    # Deduplicate by normalized form
    seen = set()
    unique = []
    for c in candidates:
        norm = _normalize(c)
        if norm not in seen:
            seen.add(norm)
            unique.append(c)
    if len(unique) < count:
        return unique
    return random.sample(unique, count)


def generate_vocab_quiz(
    course: str,
    lang: str,
    lesson: str | None = None,
    cefr: str | None = None,
    count: int = 10,
) -> list[dict]:
    """Generate vocabulary multiple-choice questions.

    Each question shows a target-language word; the user picks the correct
    translation from 4 choices.
    """
    from vocabulary import get_all_words

    words = get_all_words(course, lang)
    if not words:
        return []

    # Apply filters
    if lesson:
        words = [w for w in words if str(w.get("lesson_number")) == str(lesson)]
    if cefr:
        words = [w for w in words if w.get("cefr", "").upper() == cefr.upper()]

    if not words:
        return []

    # Select question words
    selected = random.sample(words, min(count, len(words)))

    # Build distractor pools grouped by CEFR level
    cefr_pools: dict[str, list[str]] = {}
    for w in get_all_words(course, lang):
        level = w.get("cefr", "").upper()
        cefr_pools.setdefault(level, []).append(w["translation"])

    # Fallback: all translations
    all_translations = [w["translation"] for w in get_all_words(course, lang)]

    questions = []
    for word in selected:
        correct_translation = word["translation"]
        word_cefr = word.get("cefr", "").upper()

        # Try same-CEFR distractors first, fall back to all
        pool = cefr_pools.get(word_cefr, all_translations)
        distractors = _pick_distractors(pool, correct_translation, 3)

        # If not enough same-level distractors, supplement from all
        if len(distractors) < 3:
            extra = _pick_distractors(all_translations, correct_translation, 3 - len(distractors))
            distractors.extend(extra)

        if not distractors:
            continue

        # Build shuffled choices
        choices = [{"text": correct_translation, "key": "correct"}]
        for i, d in enumerate(distractors):
            choices.append({"text": d, "key": f"wrong_{i}"})
        random.shuffle(choices)

        hint = word.get("gender", "")
        if word.get("notes"):
            hint = f"{hint} - {word['notes']}" if hint else word["notes"]

        questions.append({
            "question_type": "vocab",
            "prompt": word["target"],
            "choices": choices,
            "answer_key": "correct",
            "hint": hint or None,
            "cefr": word.get("cefr", ""),
            "word_key": word.get("word_key", ""),
        })

    return questions


def generate_fill_blank_quiz(
    course: str,
    lang: str,
    lesson: str | None = None,
    cefr: str | None = None,
    count: int = 5,
) -> list[dict]:
    """Generate fill-in-the-blank questions.

    Show the translation as the prompt; the user types the target-language word.
    """
    from vocabulary import get_all_words

    words = get_all_words(course, lang)
    if not words:
        return []

    # Apply filters
    if lesson:
        words = [w for w in words if str(w.get("lesson_number")) == str(lesson)]
    if cefr:
        words = [w for w in words if w.get("cefr", "").upper() == cefr.upper()]

    if not words:
        return []

    selected = random.sample(words, min(count, len(words)))

    questions = []
    for word in selected:
        hint_parts = []
        if word.get("gender"):
            hint_parts.append(word["gender"])
        if word.get("notes"):
            hint_parts.append(word["notes"])

        questions.append({
            "question_type": "fill_blank",
            "prompt": word["translation"],
            "answer": word["target"],
            "answer_key": word["target"],
            "hint": " - ".join(hint_parts) if hint_parts else None,
            "cefr": word.get("cefr", ""),
            "word_key": word.get("word_key", ""),
        })

    return questions


def generate_conjugation_quiz(
    course: str,
    lang: str,
    verb: str | None = None,
    tense: str | None = None,
    count: int = 5,
) -> list[dict]:
    """Generate conjugation multiple-choice questions.

    Show verb + tense + person; the user picks the correct conjugated form
    from 4 choices.
    """
    from grammar import get_conjugation_drill_data

    items = get_conjugation_drill_data(course, verb=verb, tense=tense)
    if not items:
        return []

    # Resolve i18n meaning
    for item in items:
        meaning = item.get("meaning", {})
        if isinstance(meaning, dict):
            item["meaning_text"] = meaning.get(lang, meaning.get("en", ""))
        else:
            item["meaning_text"] = meaning or ""

    selected = random.sample(items, min(count, len(items)))

    # Build distractor pool: all correct answers grouped by tense
    tense_pools: dict[str, list[str]] = {}
    for item in items:
        t = item.get("tense", "")
        tense_pools.setdefault(t, []).append(item["correct_answer"])

    # Fallback: all correct answers
    all_answers = [item["correct_answer"] for item in items]

    questions = []
    for item in selected:
        correct = item["correct_answer"]
        item_tense = item.get("tense", "")

        # Try same-tense distractors first
        pool = tense_pools.get(item_tense, all_answers)
        distractors = _pick_distractors(pool, correct, 3)

        if len(distractors) < 3:
            extra = _pick_distractors(all_answers, correct, 3 - len(distractors))
            distractors.extend(extra)

        if not distractors:
            continue

        choices = [{"text": correct, "key": "correct"}]
        for i, d in enumerate(distractors):
            choices.append({"text": d, "key": f"wrong_{i}"})
        random.shuffle(choices)

        questions.append({
            "question_type": "conjugation",
            "prompt": {
                "verb": item["verb"],
                "tense": item_tense,
                "person": item["person"],
                "meaning": item.get("meaning_text", ""),
            },
            "choices": choices,
            "answer_key": "correct",
            "hint": item.get("hint", ""),
        })

    return questions


def generate_mixed_quiz(
    course: str,
    lang: str,
    lesson: str | None = None,
    cefr: str | None = None,
    count: int = 15,
) -> list[dict]:
    """Generate a mixed quiz with proportional distribution of all 3 types."""
    # Distribute count across types (roughly 1/3 each)
    vocab_count = count // 3
    fill_count = count // 3
    conj_count = count - vocab_count - fill_count

    questions = []
    questions.extend(generate_vocab_quiz(course, lang, lesson=lesson, cefr=cefr, count=vocab_count))
    questions.extend(generate_fill_blank_quiz(course, lang, lesson=lesson, cefr=cefr, count=fill_count))
    questions.extend(generate_conjugation_quiz(course, lang, count=conj_count))

    random.shuffle(questions)
    return questions


def check_quiz_answer(question_type: str, answer: str, answer_key: str) -> dict:
    """Check a quiz answer with NFC normalization.

    For multiple-choice: exact match on the choice key.
    For fill_blank: NFC-normalized comparison of the typed text.

    Returns: {correct: bool, expected: str}
    """
    if question_type == "fill_blank":
        is_correct = _normalize(answer) == _normalize(answer_key)
        return {"correct": is_correct, "expected": answer_key}
    else:
        # Multiple choice: answer is the selected choice key
        is_correct = answer == "correct"
        return {"correct": is_correct, "expected": answer_key}
