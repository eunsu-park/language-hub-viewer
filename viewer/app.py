"""Language Hub Web Viewer - Flask Application.

Specialized viewer for language learning courses with CEFR-based progression.
Supports both single-user (AUTH_ENABLED=false) and multi-user (AUTH_ENABLED=true) modes.
"""
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache, wraps
from pathlib import Path
from types import SimpleNamespace

import yaml

from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, make_response

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import db, User, LessonRead, Bookmark, VocabularyProgress, QuizAttempt
from config import Config
from progress import (get_batch_progress, get_batch_read_status, get_batch_bookmark_status,
                      get_vocabulary_stats, get_quiz_stats, get_cefr_progress, get_study_streak)
from vocabulary import load_vocabulary, get_all_words, get_word_count
from grammar import (load_conjugations, load_grammar_rules, load_tense_rules,
                     get_verb, get_verb_list, get_tense_list, get_rule, get_rule_list,
                     get_conjugation_drill_data)
from quiz import (generate_vocab_quiz, generate_fill_blank_quiz,
                 generate_conjugation_quiz, generate_mixed_quiz, check_quiz_answer)
from srs import calculate_next_review, get_session_cards
from shared.utils.markdown_parser import parse_markdown, parse_markdown_cached, estimate_reading_time
from shared.utils.search import search, build_search_index, create_fts_table

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

AUTH_ENABLED = app.config.get("AUTH_ENABLED", False)

if AUTH_ENABLED:
    from flask_login import current_user, login_required
    from flask_wtf.csrf import CSRFProtect
    from auth import auth_bp, login_manager, register_cli

    login_manager.init_app(app)
    csrf = CSRFProtect(app)
    app.register_blueprint(auth_bp)
    register_cli(app)

    with app.app_context():
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"error": "Login required"}), 401
        return redirect(url_for("auth.login", next=request.url))

CONTENT_DIR = Config.CONTENT_DIR
SUPPORTED_LANGS = set(Config.SUPPORTED_LANGUAGES)
DEFAULT_LANG = Config.DEFAULT_LANGUAGE
LANGUAGE_NAMES = Config.LANGUAGE_NAMES


# Auth helpers
def _get_user_id():
    if AUTH_ENABLED:
        from flask_login import current_user as _cu
        return _cu.id if _cu.is_authenticated else None
    return None


def auth_required(f):
    if AUTH_ENABLED:
        from flask_login import login_required
        return login_required(f)
    return f


@app.context_processor
def inject_auth_state():
    ctx = {"auth_enabled": AUTH_ENABLED}
    if not AUTH_ENABLED:
        ctx["current_user"] = SimpleNamespace(is_authenticated=False)
    return ctx


@app.template_filter("i18n")
def i18n_filter(value, lang=None):
    """Resolve bilingual {en: ..., ko: ...} dicts to a single string."""
    if isinstance(value, dict):
        lang = lang or DEFAULT_LANG
        return value.get(lang, value.get("en", str(value)))
    return value or ""


@app.template_filter("timeago")
def timeago_filter(dt):
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    elif seconds < 604800:
        return f"{int(seconds // 86400)}d ago"
    else:
        return dt.strftime("%Y-%m-%d")


def validate_lang(f):
    @wraps(f)
    def decorated_function(lang, *args, **kwargs):
        if lang not in SUPPORTED_LANGS:
            abort(404)
        return f(lang, *args, **kwargs)
    return decorated_function


# Course metadata loading
_course_cache: dict[str, dict] = {}


def load_course_metadata(course: str) -> dict:
    """Load course_metadata.yaml for a target language course."""
    if course in _course_cache:
        return _course_cache[course]

    yaml_path = CONTENT_DIR / course / "course_metadata.yaml"
    if not yaml_path.exists():
        _course_cache[course] = {}
        return {}

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _course_cache[course] = data
    return data


_cefr_cache = None


def load_cefr_levels() -> dict:
    """Load CEFR level definitions from _shared/cefr_levels.yaml."""
    global _cefr_cache
    if _cefr_cache is not None:
        return _cefr_cache

    yaml_path = CONTENT_DIR / "_shared" / "cefr_levels.yaml"
    if not yaml_path.exists():
        _cefr_cache = {"levels": []}
        return _cefr_cache

    with open(yaml_path, encoding="utf-8") as f:
        _cefr_cache = yaml.safe_load(f) or {"levels": []}
    return _cefr_cache


def get_courses() -> list[dict]:
    """Get list of available language courses."""
    courses = []
    if not CONTENT_DIR.exists():
        return courses
    for course_dir in sorted(CONTENT_DIR.iterdir()):
        if not course_dir.is_dir() or course_dir.name.startswith("_"):
            continue
        meta = load_course_metadata(course_dir.name)
        if not meta:
            continue
        lang_info = meta.get("language", {})
        stages = meta.get("stages", [])
        total_lessons = sum(len(s.get("lessons", [])) for s in stages)
        courses.append({
            "name": course_dir.name,
            "display_name": lang_info.get("name", {}).get("native", course_dir.name),
            "code": lang_info.get("code", ""),
            "label": lang_info.get("name", {}),
            "cefr_range": f"{stages[0]['cefr']}-{stages[-1]['cefr']}" if stages else "",
            "total_lessons": total_lessons,
            "stages": stages,
        })
    return courses


def get_course_lang(course: str) -> dict:
    """Extract language config from course metadata for template use.

    Returns a dict with keys: word_key, tts_locale, accent_chars, name.
    Falls back to Spanish defaults if not specified in metadata.
    """
    meta = load_course_metadata(course)
    lang_info = meta.get("language", {})
    return {
        "word_key": lang_info.get("word_key", course.lower()),
        "tts_locale": lang_info.get("tts_locale", "es-ES"),
        "accent_chars": lang_info.get("accent_chars", ["á", "é", "í", "ó", "ú", "ñ", "ü"]),
        "name": lang_info.get("name", {}),
    }


def get_content_dir(course: str, lang: str) -> Path:
    """Get content directory: content/<Course>/<lang>/"""
    return CONTENT_DIR / course / lang


def get_lessons(course: str, lang: str) -> list[dict]:
    """Get all lessons for a course in a specific instruction language."""
    content_dir = get_content_dir(course, lang)
    if not content_dir.exists():
        return []
    mtime = content_dir.stat().st_mtime
    return [dict(l) for l in _get_lessons_cached(course, lang, mtime)]


@lru_cache(maxsize=128)
def _get_lessons_cached(course: str, lang: str, dir_mtime: float) -> tuple:
    content_dir = get_content_dir(course, lang)
    lessons = []
    for md_file in sorted(content_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        title = _extract_title(content) or md_file.stem
        lessons.append({
            "filename": md_file.name,
            "title": title,
            "display_name": md_file.stem.replace("_", " "),
            "reading_time": estimate_reading_time(content),
        })
    return tuple(lessons)


def _extract_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def get_available_languages() -> list[dict]:
    return [{"code": lang, "name": LANGUAGE_NAMES.get(lang, lang)} for lang in SUPPORTED_LANGS]


def get_stage_lessons(course: str, lang: str) -> list[dict]:
    """Get lessons organized by CEFR stages."""
    meta = load_course_metadata(course)
    stages = meta.get("stages", [])
    all_lessons = get_lessons(course, lang)
    lesson_map = {l["filename"]: l for l in all_lessons}

    result = []
    for stage in stages:
        stage_lessons = []
        for lesson_num in stage.get("lessons", []):
            # Find lesson file starting with this number
            for fname, lesson in lesson_map.items():
                if fname.startswith(f"{lesson_num}_"):
                    stage_lessons.append(lesson)
                    break
        result.append({
            "id": stage["id"],
            "cefr": stage["cefr"],
            "label": stage.get("label", {}),
            "description": stage.get("description", {}),
            "lessons": stage_lessons,
        })
    return result


# Routes
@app.route("/")
def root():
    lang = request.cookies.get("lang", DEFAULT_LANG)
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return redirect(url_for("index", lang=lang))


@app.route("/<lang>/")
@validate_lang
def index(lang: str):
    """Home page - course selection grid."""
    courses = get_courses()
    user_id = _get_user_id()

    # Get progress per course
    for course in courses:
        topics = [{"name": course["name"], "lesson_count": course["total_lessons"]}]
        progress = get_batch_progress(lang, user_id, topics)
        course["progress"] = progress.get(course["name"], {"total": 0, "read": 0, "percentage": 0})

    response = make_response(render_template(
        "home.html",
        courses=courses,
        lang=lang,
        languages=get_available_languages(),
    ))
    response.set_cookie("lang", lang, max_age=60*60*24*365)
    return response


@app.route("/<lang>/course/<course_name>")
@validate_lang
def course_home(lang: str, course_name: str):
    """Course home - CEFR stages with lessons."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})
    staged_lessons = get_stage_lessons(course_name, lang)
    user_id = _get_user_id()
    cefr_data = load_cefr_levels()
    cefr_levels_raw = cefr_data.get("levels", {})
    cefr_levels = {k.lower(): v for k, v in cefr_levels_raw.items()} if isinstance(cefr_levels_raw, dict) else {}

    # Get read/bookmark status for all lessons
    all_filenames = []
    for stage in staged_lessons:
        for lesson in stage["lessons"]:
            all_filenames.append(lesson["filename"])

    read_status = get_batch_read_status(lang, course_name, user_id, all_filenames)
    bookmark_status = get_batch_bookmark_status(lang, course_name, user_id, all_filenames)

    for stage in staged_lessons:
        stage_read = 0
        for lesson in stage["lessons"]:
            lesson["is_read"] = read_status.get(lesson["filename"], False)
            lesson["is_bookmarked"] = bookmark_status.get(lesson["filename"], False)
            if lesson["is_read"]:
                stage_read += 1
        stage_total = len(stage["lessons"])
        stage["progress"] = {
            "total": stage_total,
            "read": stage_read,
            "percentage": round(stage_read / stage_total * 100) if stage_total > 0 else 0,
        }
        # CEFR color
        cefr_key = stage["cefr"].split("-")[0].lower()  # "B2-C1" -> "b2"
        cefr_info = cefr_levels.get(cefr_key, {})
        stage["color"] = cefr_info.get("color", "#6c757d")

    # Overall progress
    total = len(all_filenames)
    read_count = sum(1 for v in read_status.values() if v)
    overall = {
        "total": total,
        "read": read_count,
        "percentage": round(read_count / total * 100) if total > 0 else 0,
    }

    # Continue learning: find first unread lesson
    continue_lesson = None
    for stage in staged_lessons:
        for lesson in stage["lessons"]:
            if not lesson["is_read"] and not lesson["filename"].startswith("00_"):
                continue_lesson = lesson
                break
        if continue_lesson:
            break

    return render_template(
        "course_home.html",
        course=course_name,
        course_label=lang_info.get("name", {}),
        course_display=lang_info.get("name", {}).get("native", course_name),
        staged_lessons=staged_lessons,
        overall=overall,
        continue_lesson=continue_lesson,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/course/<course_name>/lesson/<filename>")
@validate_lang
def lesson(lang: str, course_name: str, filename: str):
    """Lesson page - render markdown content."""
    filepath = get_content_dir(course_name, lang) / filename
    if not filepath.exists():
        abort(404)

    parsed = parse_markdown_cached(str(filepath))
    user_id = _get_user_id()

    lessons = get_lessons(course_name, lang)
    current_idx = next(
        (i for i, l in enumerate(lessons) if l["filename"] == filename), -1
    )
    if current_idx < 0:
        prev_lesson = next_lesson = None
    else:
        prev_lesson = lessons[current_idx - 1] if current_idx > 0 else None
        next_lesson = lessons[current_idx + 1] if current_idx < len(lessons) - 1 else None

    # Read/bookmark status
    is_read = False
    is_bm = False
    if AUTH_ENABLED:
        if user_id:
            is_read = LessonRead.query.filter_by(
                user_id=user_id, language=lang, topic=course_name, filename=filename
            ).first() is not None
            is_bm = Bookmark.query.filter_by(
                user_id=user_id, language=lang, topic=course_name, filename=filename
            ).first() is not None
    else:
        is_read = LessonRead.query.filter_by(
            user_id=None, language=lang, topic=course_name, filename=filename
        ).first() is not None
        is_bm = Bookmark.query.filter_by(
            user_id=None, language=lang, topic=course_name, filename=filename
        ).first() is not None

    # Extract lesson number from filename for vocabulary tooltips
    lesson_num = None
    lesson_match = re.match(r'^(\d+)', filename)
    if lesson_match:
        lesson_num = int(lesson_match.group(1))

    lesson_vocab = []
    if lesson_num:
        all_words = get_all_words(course_name, lang)
        lesson_vocab = [w for w in all_words if w.get("lesson_number") == lesson_num]

    return render_template(
        "lesson.html",
        course=course_name,
        filename=filename,
        title=parsed["title"] or filename,
        content=parsed["html"],
        toc=parsed["toc"],
        is_read=is_read,
        is_bookmarked=is_bm,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
        lesson_vocab=lesson_vocab,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/search")
@validate_lang
def search_page(lang: str):
    """Search page."""
    query = request.args.get("q", "")
    results = []
    if query:
        db_path = Path(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
        results = search(db_path, query, lang=lang)
    return render_template(
        "search.html",
        query=query,
        results=results,
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/dashboard")
@validate_lang
@auth_required
def dashboard(lang: str):
    """Dashboard page - enhanced CEFR progress across courses."""
    courses = get_courses()
    user_id = _get_user_id()

    # Existing per-course progress
    for course in courses:
        topics = [{"name": course["name"], "lesson_count": course["total_lessons"]}]
        progress = get_batch_progress(lang, user_id, topics)
        course["progress"] = progress.get(course["name"], {"total": 0, "read": 0, "percentage": 0})

    total_lessons = sum(c["total_lessons"] for c in courses)
    total_read = sum(c["progress"]["read"] for c in courses)
    overall = {
        "total": total_lessons,
        "read": total_read,
        "percentage": round(total_read / total_lessons * 100) if total_lessons > 0 else 0,
    }

    # Extended stats (use first course since we primarily have Spanish)
    course_name = courses[0]["name"] if courses else "Spanish"
    vocab_stats = get_vocabulary_stats(user_id, course_name)
    quiz_stats = get_quiz_stats(user_id, course_name)
    total_words = get_word_count(course_name)
    streak = get_study_streak(user_id)

    # CEFR progress breakdown
    metadata = courses[0] if courses else {}
    stages = metadata.get("stages", [])
    cefr_progress = get_cefr_progress(user_id, course_name, lang, stages)

    return render_template(
        "dashboard.html",
        courses=courses, overall=overall,
        vocab_stats=vocab_stats, quiz_stats=quiz_stats,
        total_words=total_words, streak=streak,
        cefr_progress=cefr_progress, stages=stages,
        lang=lang, languages=get_available_languages(),
    )


@app.route("/<lang>/bookmarks")
@validate_lang
@auth_required
def bookmarks(lang: str):
    """Bookmarks page."""
    user_id = _get_user_id()
    bookmarked = Bookmark.query.filter_by(user_id=user_id, language=lang) \
        .order_by(Bookmark.created_at.desc()).all()

    unique_courses = {bm.topic for bm in bookmarked}
    lessons_by_course = {c: get_lessons(c, lang) for c in unique_courses}

    items = []
    for bm in bookmarked:
        lessons = lessons_by_course.get(bm.topic, [])
        lesson_info = next((l for l in lessons if l["filename"] == bm.filename), None)
        if lesson_info:
            items.append({
                "course": bm.topic,
                "filename": bm.filename,
                "title": lesson_info["title"],
                "created_at": bm.created_at,
            })
    return render_template(
        "bookmarks.html",
        bookmarks=items,
        lang=lang,
        languages=get_available_languages(),
    )


# API Routes
@app.route("/api/mark-read", methods=["POST"])
@auth_required
def api_mark_read():
    data = request.get_json()
    lang = data.get("lang", DEFAULT_LANG)
    course_name = data.get("topic")  # reuse 'topic' key for DB compat
    filename = data.get("filename")
    is_read = data.get("is_read", True)

    if lang not in SUPPORTED_LANGS:
        return jsonify({"error": "Unsupported language"}), 400
    if not course_name or not filename:
        return jsonify({"error": "Missing topic or filename"}), 400

    user_id = _get_user_id()
    existing = LessonRead.query.filter_by(
        user_id=user_id, language=lang, topic=course_name, filename=filename
    ).first()

    if is_read and not existing:
        lesson_read = LessonRead(user_id=user_id, language=lang, topic=course_name, filename=filename)
        db.session.add(lesson_read)
        db.session.commit()
    elif not is_read and existing:
        db.session.delete(existing)
        db.session.commit()

    return jsonify({"success": True, "is_read": is_read})


@app.route("/api/bookmark", methods=["POST"])
@auth_required
def api_bookmark():
    data = request.get_json()
    lang = data.get("lang", DEFAULT_LANG)
    course_name = data.get("topic")
    filename = data.get("filename")

    if lang not in SUPPORTED_LANGS:
        return jsonify({"error": "Unsupported language"}), 400
    if not course_name or not filename:
        return jsonify({"error": "Missing topic or filename"}), 400

    user_id = _get_user_id()
    existing = Bookmark.query.filter_by(
        user_id=user_id, language=lang, topic=course_name, filename=filename
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"success": True, "bookmarked": False})
    else:
        bookmark = Bookmark(user_id=user_id, language=lang, topic=course_name, filename=filename)
        db.session.add(bookmark)
        db.session.commit()
        return jsonify({"success": True, "bookmarked": True})


@app.route("/api/clear-user-data", methods=["POST"])
@auth_required
def api_clear_user_data():
    user_id = _get_user_id()
    deleted_reads = LessonRead.query.filter_by(user_id=user_id).delete()
    deleted_bookmarks = Bookmark.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({
        "success": True,
        "deleted_reads": deleted_reads,
        "deleted_bookmarks": deleted_bookmarks,
    })


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    lang = request.args.get("lang", DEFAULT_LANG)
    if not query:
        return jsonify({"results": []})

    db_path = Path(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    results = search(db_path, query, lang=lang)
    return jsonify({"results": results})


@app.route("/api/set-language", methods=["POST"])
def api_set_language():
    data = request.get_json()
    lang = data.get("lang", DEFAULT_LANG)
    if lang not in SUPPORTED_LANGS:
        return jsonify({"error": "Unsupported language"}), 400
    response = jsonify({"success": True, "lang": lang})
    response.set_cookie("lang", lang, max_age=60*60*24*365)
    return response


# Vocabulary Routes
@app.route("/<lang>/course/<course_name>/vocabulary")
@validate_lang
def vocabulary_index(lang: str, course_name: str):
    """Vocabulary list with filtering."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})
    words = get_all_words(course_name, lang)
    total_count = len(words)

    # Collect unique CEFR levels and lesson numbers for filter UI
    cefr_set = sorted({w["cefr"] for w in words if w.get("cefr")})
    # Build lesson list with number and title for dropdown
    lesson_map = {}
    for w in words:
        num = w.get("lesson_number")
        if num and num not in lesson_map:
            lesson_map[num] = w.get("lesson", "")
    lesson_list = sorted(
        [{"number": str(n), "title": t} for n, t in lesson_map.items()],
        key=lambda x: int(x["number"]) if x["number"].isdigit() else 0,
    )

    # Current filter state from query params
    filters = {
        "cefr": request.args.get("cefr", ""),
        "lesson": request.args.get("lesson", ""),
        "q": request.args.get("q", ""),
    }

    return render_template(
        "vocabulary/index.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        words=words,
        total_count=total_count,
        cefr_levels=cefr_set,
        lessons=lesson_list,
        filters=filters,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/course/<course_name>/flashcard")
@validate_lang
def flashcard_page(lang: str, course_name: str):
    """Flashcard study page."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})

    return render_template(
        "vocabulary/flashcard.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/api/flashcard/session")
@auth_required
def api_flashcard_session():
    """Get cards for a flashcard study session."""
    course = request.args.get("course")
    lang = request.args.get("lang", DEFAULT_LANG)
    cefr = request.args.get("cefr")
    lesson = request.args.get("lesson")

    if not course:
        return jsonify({"error": "Missing course"}), 400

    user_id = _get_user_id()
    cards = get_session_cards(user_id, course, lang,
                              cefr_filter=cefr, lesson_filter=lesson)

    return jsonify({"cards": cards, "total": len(cards)})


@app.route("/api/flashcard/grade", methods=["POST"])
@auth_required
def api_flashcard_grade():
    """Grade a flashcard and update SRS state."""
    data = request.get_json()
    course = data.get("course")
    word_key = data.get("word_key")
    quality = data.get("quality")  # 0-3

    if not all([course, word_key, quality is not None]):
        return jsonify({"error": "Missing fields"}), 400

    # Template sends 1-4 (Again/Hard/Good/Easy), SM-2 expects 0-3
    quality = max(0, min(3, int(quality) - 1))
    user_id = _get_user_id()
    now = datetime.now(timezone.utc)

    # Find or create progress record
    progress = VocabularyProgress.query.filter_by(
        user_id=user_id, course=course, word_key=word_key
    ).first()

    if not progress:
        progress = VocabularyProgress(
            user_id=user_id, course=course, word_key=word_key
        )
        db.session.add(progress)

    # Calculate next review using SM-2 (use defaults for new records)
    result = calculate_next_review(
        progress.ease_factor or 2.5,
        progress.interval or 0,
        progress.repetitions or 0,
        quality,
    )

    progress.ease_factor = result["ease_factor"]
    progress.interval = result["interval"]
    progress.repetitions = result["repetitions"]
    progress.next_review = result["next_review"]
    progress.last_reviewed = now

    db.session.commit()

    return jsonify({
        "success": True,
        "next_review": progress.next_review.isoformat() if progress.next_review else None,
        "interval": progress.interval,
        "ease_factor": round(progress.ease_factor, 2),
    })


# Grammar Routes
@app.route("/<lang>/course/<course_name>/grammar")
@validate_lang
def grammar_index(lang: str, course_name: str):
    """Grammar reference index page."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})
    rules = get_rule_list(course_name)
    tenses = get_tense_list(course_name)
    verbs = get_verb_list(course_name)

    return render_template(
        "grammar/index.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        rules=rules,
        tenses=tenses,
        verbs=verbs,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/course/<course_name>/grammar/verb/<verb>")
@validate_lang
def grammar_verb(lang: str, course_name: str, verb: str):
    """Verb conjugation detail page."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})
    verb_data = get_verb(course_name, verb)
    if verb_data is None:
        abort(404)

    tenses = get_tense_list(course_name)

    return render_template(
        "grammar/conjugation.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        verb_name=verb,
        verb=verb_data,
        tenses=tenses,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/course/<course_name>/grammar/rule/<rule_id>")
@validate_lang
def grammar_rule(lang: str, course_name: str, rule_id: str):
    """Grammar rule detail page."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})
    rule_data = get_rule(course_name, rule_id)
    if rule_data is None:
        abort(404)

    return render_template(
        "grammar/rule.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        rule_id=rule_id,
        rule=rule_data,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


# Practice Routes
@app.route("/<lang>/course/<course_name>/practice")
@validate_lang
def practice_hub(lang: str, course_name: str):
    """Practice hub - choose practice type."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})

    return render_template(
        "practice/hub.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/<lang>/course/<course_name>/practice/conjugation")
@validate_lang
def conjugation_drill(lang: str, course_name: str):
    """Conjugation drill page."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})
    verbs = get_verb_list(course_name)
    tenses = get_tense_list(course_name)

    return render_template(
        "practice/conjugation.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        verbs=verbs,
        tenses=tenses,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


def _normalize_accent(text: str) -> str:
    """Normalize accented characters for lenient comparison."""
    return unicodedata.normalize("NFC", text.lower().strip())


@app.route("/api/practice/conjugation", methods=["POST"])
@auth_required
def api_check_conjugation():
    """Check a conjugation answer."""
    data = request.get_json()
    course = data.get("course")
    verb = data.get("verb")
    tense = data.get("tense")
    person = data.get("person")
    answer = data.get("answer", "").strip()

    if not all([course, verb, tense, person]):
        return jsonify({"error": "Missing fields"}), 400

    verb_data = get_verb(course, verb)
    if not verb_data:
        return jsonify({"error": "Verb not found"}), 404

    tense_forms = verb_data.get("tenses", {}).get(tense, {})
    expected = tense_forms.get(person)
    if expected is None:
        return jsonify({"error": "Form not found"}), 404

    correct = _normalize_accent(answer) == _normalize_accent(expected)

    return jsonify({
        "correct": correct,
        "expected": expected,
        "answer": answer,
        "verb": verb,
        "tense": tense,
        "person": person,
    })


@app.route("/api/practice/drill-set")
@auth_required
def api_drill_set():
    """Get a set of conjugation drill questions."""
    course = request.args.get("course")
    verb = request.args.get("verb")  # optional filter
    tense = request.args.get("tense")  # optional filter
    lang = request.args.get("lang", DEFAULT_LANG)

    if not course:
        return jsonify({"error": "Missing course"}), 400

    items = get_conjugation_drill_data(course, verb=verb, tense=tense)

    # Resolve i18n meaning fields
    for item in items:
        meaning = item.get("meaning", {})
        if isinstance(meaning, dict):
            item["meaning_text"] = meaning.get(lang, meaning.get("en", ""))
        else:
            item["meaning_text"] = meaning or ""

    return jsonify({"items": items, "total": len(items)})


# Quiz Routes
@app.route("/<lang>/course/<course_name>/practice/quiz")
@validate_lang
def quiz_page(lang: str, course_name: str):
    """Quiz page with multiple question types."""
    course_dir = CONTENT_DIR / course_name
    if not course_dir.exists():
        abort(404)

    meta = load_course_metadata(course_name)
    lang_info = meta.get("language", {})

    # Load filter options from vocabulary data
    words = get_all_words(course_name, lang)
    cefr_set = sorted({w["cefr"] for w in words if w.get("cefr")})
    lesson_map = {}
    for w in words:
        num = w.get("lesson_number")
        if num and num not in lesson_map:
            lesson_map[num] = w.get("lesson", "")
    lesson_list = sorted(
        [{"number": str(n), "title": t} for n, t in lesson_map.items()],
        key=lambda x: int(x["number"]) if x["number"].isdigit() else 0,
    )

    return render_template(
        "practice/quiz.html",
        course=course_name,
        course_display=lang_info.get("name", {}).get("native", course_name),
        cefr_levels=cefr_set,
        lessons=lesson_list,
        course_lang=get_course_lang(course_name),
        lang=lang,
        languages=get_available_languages(),
    )


@app.route("/api/practice/quiz-set")
@auth_required
def api_quiz_set():
    """Generate a set of quiz questions."""
    course = request.args.get("course")
    lang = request.args.get("lang", DEFAULT_LANG)
    quiz_type = request.args.get("quiz_type", "mixed")
    cefr = request.args.get("cefr")
    lesson = request.args.get("lesson")
    count = request.args.get("count", "15")

    if not course:
        return jsonify({"error": "Missing course"}), 400

    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 15
    count = max(1, min(count, 50))

    if quiz_type == "vocab":
        questions = generate_vocab_quiz(course, lang, lesson=lesson, cefr=cefr, count=count)
    elif quiz_type == "fill_blank":
        questions = generate_fill_blank_quiz(course, lang, lesson=lesson, cefr=cefr, count=count)
    elif quiz_type == "conjugation":
        questions = generate_conjugation_quiz(course, lang, count=count)
    else:
        questions = generate_mixed_quiz(course, lang, lesson=lesson, cefr=cefr, count=count)

    return jsonify({"questions": questions, "total": len(questions)})


@app.route("/api/practice/quiz-answer", methods=["POST"])
@auth_required
def api_quiz_answer():
    """Check an individual quiz answer."""
    data = request.get_json()
    question_type = data.get("question_type")
    answer = data.get("answer", "")
    answer_key = data.get("answer_key", "")

    if not question_type:
        return jsonify({"error": "Missing question_type"}), 400

    result = check_quiz_answer(question_type, answer, answer_key)
    return jsonify(result)


@app.route("/api/practice/quiz-complete", methods=["POST"])
@auth_required
def api_quiz_complete():
    """Save a completed quiz session."""
    data = request.get_json()
    course = data.get("course")
    quiz_type = data.get("quiz_type", "mixed")
    score = data.get("score", 0)
    total = data.get("total", 0)
    lesson_filter = data.get("lesson_filter")
    cefr_filter = data.get("cefr_filter")

    if not course:
        return jsonify({"error": "Missing course"}), 400

    user_id = _get_user_id()
    attempt = QuizAttempt(
        user_id=user_id,
        course=course,
        quiz_type=quiz_type,
        score=score,
        total=total,
        lesson_filter=lesson_filter,
        cefr_filter=cefr_filter,
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({
        "success": True,
        "id": attempt.id,
        "score": score,
        "total": total,
    })


# CLI Commands
@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.create_all()
        db_path = Path(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
        create_fts_table(db_path)
        print("Database initialized.")


@app.cli.command("build-index")
def build_index():
    db_path = Path(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    # Index lessons from each course in each instruction language
    for course_dir in sorted(CONTENT_DIR.iterdir()):
        if not course_dir.is_dir() or course_dir.name.startswith("_"):
            continue
        for lang in SUPPORTED_LANGS:
            lang_dir = course_dir / lang
            if lang_dir.exists():
                print(f"Building index for {course_dir.name}/{lang}...")
                build_search_index(lang_dir, db_path, lang=lang)
    print("Search index built.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5060)
