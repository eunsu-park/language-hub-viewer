"""SM-2 Spaced Repetition System engine."""
from datetime import datetime, timedelta, timezone

from models import db, VocabularyProgress
from vocabulary import get_all_words


# ---------------------------------------------------------------------------
# SM-2 algorithm
# ---------------------------------------------------------------------------

def calculate_next_review(
    ease_factor: float,
    interval: int,
    repetitions: int,
    quality: int,
) -> dict:
    """Apply the SM-2 algorithm and return updated card state.

    Parameters
    ----------
    ease_factor : float
        Current ease factor (>= 1.3).
    interval : int
        Current interval in days.
    repetitions : int
        Number of consecutive successful reviews.
    quality : int
        User grade: 0 = Again, 1 = Hard, 2 = Good, 3 = Easy.

    Returns
    -------
    dict
        Keys: ``ease_factor``, ``interval``, ``repetitions``, ``next_review``.
    """
    quality = max(0, min(3, quality))

    # Ease factor adjustment: ef = ef + (0.1 - (3-q) * (0.08 + (3-q) * 0.02))
    ef = ease_factor + (0.1 - (3 - quality) * (0.08 + (3 - quality) * 0.02))
    ef = max(ef, 1.3)

    if quality < 2:
        # Failed review — reset
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        repetitions += 1

    next_review = datetime.now(timezone.utc) + timedelta(days=interval)

    return {
        "ease_factor": round(ef, 4),
        "interval": interval,
        "repetitions": repetitions,
        "next_review": next_review,
    }


# ---------------------------------------------------------------------------
# Card retrieval helpers
# ---------------------------------------------------------------------------

def get_due_cards(user_id: int | None, course: str, limit: int = 20) -> list:
    """Query VocabularyProgress for cards due for review.

    A card is due when ``next_review <= now``.  Results are ordered by
    ``next_review`` ascending (most overdue first).
    """
    now = datetime.now(timezone.utc)
    query = VocabularyProgress.query.filter(
        VocabularyProgress.course == course,
        VocabularyProgress.next_review <= now,
    )

    if user_id is not None:
        query = query.filter(VocabularyProgress.user_id == user_id)
    else:
        query = query.filter(VocabularyProgress.user_id.is_(None))

    return query.order_by(VocabularyProgress.next_review.asc()).limit(limit).all()


def get_new_cards(
    user_id: int | None,
    course: str,
    lang: str,
    limit: int = 10,
    cefr_filter: str | None = None,
    lesson_filter: str | None = None,
) -> list:
    """Get vocabulary words the user has not studied yet.

    Compares the full word list from the YAML files against existing
    ``VocabularyProgress`` rows and returns those without a row.
    """
    all_words = get_all_words(course, lang)
    if not all_words:
        return []

    # Apply optional filters
    if cefr_filter:
        all_words = [w for w in all_words if w.get("cefr", "").upper() == cefr_filter.upper()]
    if lesson_filter:
        all_words = [w for w in all_words if str(w.get("lesson_number", "")) == str(lesson_filter)]

    # Fetch all word_keys the user already has progress for
    query = VocabularyProgress.query.filter(
        VocabularyProgress.course == course,
    )
    if user_id is not None:
        query = query.filter(VocabularyProgress.user_id == user_id)
    else:
        query = query.filter(VocabularyProgress.user_id.is_(None))

    known_keys = {row.word_key for row in query.all()}

    new: list[dict] = []
    for word in all_words:
        wk = word.get("word_key") or _make_word_key(word)
        if wk not in known_keys:
            new.append({**word, "word_key": wk})
            if len(new) >= limit:
                break
    return new


def get_session_cards(
    user_id: int | None,
    course: str,
    lang: str,
    new_limit: int = 10,
    review_limit: int = 20,
    cefr_filter: str | None = None,
    lesson_filter: str | None = None,
) -> list:
    """Build a study session: mix of new cards and due review cards.

    Due cards are returned first (most overdue), followed by new cards up
    to their respective limits.
    """
    # Build word lookup for enriching review cards
    all_words = get_all_words(course, lang)
    word_lookup = {}
    for w in all_words:
        wk = w.get("word_key") or _make_word_key(w)
        word_lookup[wk] = w

    due = get_due_cards(user_id, course, limit=review_limit)
    review_cards = [_progress_to_dict(p, word_lookup) for p in due]

    # Filter review cards if filters are active
    if cefr_filter:
        review_cards = [c for c in review_cards if c.get("cefr", "").upper() == cefr_filter.upper()]
    if lesson_filter:
        review_cards = [c for c in review_cards if str(c.get("lesson_number", "")) == str(lesson_filter)]

    new = get_new_cards(user_id, course, lang, limit=new_limit,
                        cefr_filter=cefr_filter, lesson_filter=lesson_filter)
    new_cards = [{"type": "new", **w} for w in new]

    return review_cards + new_cards


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_word_key(word: dict) -> str:
    """Build a unique key for a word: ``lesson_number:category:spanish``."""
    return f"{word.get('lesson_number', 0)}:{word.get('category', '')}:{word.get('spanish', '')}"


def _progress_to_dict(progress: VocabularyProgress, word_lookup: dict | None = None) -> dict:
    """Convert a VocabularyProgress row to a session card dict.

    If *word_lookup* is provided, enrich the dict with vocabulary data
    (target word, translation, gender, cefr, lesson info).
    """
    card = {
        "type": "review",
        "id": progress.id,
        "word_key": progress.word_key,
        "course": progress.course,
        "ease_factor": progress.ease_factor,
        "interval": progress.interval,
        "repetitions": progress.repetitions,
        "next_review": progress.next_review.isoformat() if progress.next_review else None,
        "last_reviewed": progress.last_reviewed.isoformat() if progress.last_reviewed else None,
    }

    # Enrich with vocabulary data
    if word_lookup and progress.word_key in word_lookup:
        w = word_lookup[progress.word_key]
        card.update({
            "target": w.get("target", w.get("spanish", "")),
            "translation": w.get("translation", ""),
            "gender": w.get("gender", ""),
            "cefr": w.get("cefr", ""),
            "lesson": w.get("lesson", ""),
            "lesson_number": w.get("lesson_number", 0),
        })
    else:
        # Fallback: parse word_key "lesson_num:category:spanish"
        parts = progress.word_key.split(":", 2)
        card["target"] = parts[2] if len(parts) > 2 else progress.word_key
        card["translation"] = ""

    return card
