"""Batch progress queries to eliminate N+1 query patterns."""
from sqlalchemy import func

from models import db, LessonRead, Bookmark


def get_batch_progress(lang: str, user_id: int | None, topics: list[dict]) -> dict[str, dict]:
    """Get reading progress for all topics in a single query."""
    query = db.session.query(
        LessonRead.topic,
        func.count(LessonRead.id)
    ).filter(
        LessonRead.language == lang
    )

    if user_id is not None:
        query = query.filter(LessonRead.user_id == user_id)
    else:
        query = query.filter(LessonRead.user_id.is_(None))

    read_counts = dict(query.group_by(LessonRead.topic).all())

    progress = {}
    for topic in topics:
        name = topic["name"]
        total = topic["lesson_count"]
        read = read_counts.get(name, 0)
        progress[name] = {
            "total": total,
            "read": read,
            "percentage": round(read / total * 100) if total > 0 else 0,
        }
    return progress


def get_batch_read_status(lang: str, topic: str, user_id: int | None,
                          filenames: list[str]) -> dict[str, bool]:
    """Get read status for all lessons in a topic in a single query."""
    query = LessonRead.query.filter(
        LessonRead.language == lang,
        LessonRead.topic == topic,
    )
    if user_id is not None:
        query = query.filter(LessonRead.user_id == user_id)
    else:
        query = query.filter(LessonRead.user_id.is_(None))

    read_filenames = {r.filename for r in query.all()}
    return {f: f in read_filenames for f in filenames}


def get_batch_bookmark_status(lang: str, topic: str, user_id: int | None,
                              filenames: list[str]) -> dict[str, bool]:
    """Get bookmark status for all lessons in a topic in a single query."""
    query = Bookmark.query.filter(
        Bookmark.language == lang,
        Bookmark.topic == topic,
    )
    if user_id is not None:
        query = query.filter(Bookmark.user_id == user_id)
    else:
        query = query.filter(Bookmark.user_id.is_(None))

    bookmarked_filenames = {b.filename for b in query.all()}
    return {f: f in bookmarked_filenames for f in filenames}


def get_vocabulary_stats(user_id: int | None, course: str) -> dict:
    """Get vocabulary SRS statistics.

    Returns: {total: int, learning: int, mastered: int, due_today: int}
    """
    from datetime import datetime, timezone

    from models import VocabularyProgress

    base = VocabularyProgress.query.filter_by(course=course)
    if user_id is not None:
        base = base.filter_by(user_id=user_id)
    else:
        base = base.filter(VocabularyProgress.user_id.is_(None))

    all_progress = base.all()
    now = datetime.now(timezone.utc)

    total = len(all_progress)
    mastered = sum(1 for p in all_progress if p.interval >= 21)  # 21+ days interval = mastered
    learning = total - mastered
    due_today = sum(1 for p in all_progress if p.next_review and p.next_review <= now)

    return {"total": total, "learning": learning, "mastered": mastered, "due_today": due_today}


def get_quiz_stats(user_id: int | None, course: str) -> dict:
    """Get quiz attempt statistics.

    Returns: {attempts: int, avg_score: float, best_score: float, by_type: {type: {attempts, avg}}}
    """
    # Import QuizAttempt — it may or may not exist yet, handle gracefully
    try:
        from models import QuizAttempt
    except ImportError:
        return {"attempts": 0, "avg_score": 0, "best_score": 0, "by_type": {}}

    base = QuizAttempt.query.filter_by(course=course)
    if user_id is not None:
        base = base.filter_by(user_id=user_id)
    else:
        base = base.filter(QuizAttempt.user_id.is_(None))

    attempts = base.all()
    if not attempts:
        return {"attempts": 0, "avg_score": 0, "best_score": 0, "by_type": {}}

    scores = [a.score / a.total * 100 if a.total > 0 else 0 for a in attempts]
    by_type: dict[str, dict] = {}
    for a in attempts:
        if a.quiz_type not in by_type:
            by_type[a.quiz_type] = {"attempts": 0, "total_pct": 0}
        by_type[a.quiz_type]["attempts"] += 1
        by_type[a.quiz_type]["total_pct"] += (a.score / a.total * 100 if a.total > 0 else 0)

    for t in by_type:
        by_type[t]["avg"] = round(by_type[t]["total_pct"] / by_type[t]["attempts"])
        del by_type[t]["total_pct"]

    return {
        "attempts": len(attempts),
        "avg_score": round(sum(scores) / len(scores)),
        "best_score": round(max(scores)),
        "by_type": by_type,
    }


def get_cefr_progress(user_id: int | None, course: str, lang: str,
                      stages: list[dict]) -> dict[str, dict]:
    """Get progress broken down by CEFR stage.

    stages: list of stage dicts from course_metadata (each has 'id', 'cefr', 'lessons')
    Returns: {stage_id: {cefr, lessons_read, lessons_total, percentage}}
    """
    # Get all read filenames for this course
    query = LessonRead.query.filter(
        LessonRead.language == lang,
        LessonRead.topic == course,
    )
    if user_id is not None:
        query = query.filter(LessonRead.user_id == user_id)
    else:
        query = query.filter(LessonRead.user_id.is_(None))

    read_filenames = {r.filename for r in query.all()}

    result = {}
    for stage in stages:
        stage_id = stage.get("id", "")
        cefr = stage.get("cefr", stage.get("jlpt", stage.get("topik", stage.get("hanja_level", ""))))
        lesson_nums = stage.get("lessons", [])
        total = len(lesson_nums)
        # Count how many lesson filenames start with these numbers
        read = sum(
            1 for num in lesson_nums
            if any(f.startswith(f"{num}_") or f.startswith(f"0{num}_") for f in read_filenames)
        )
        result[stage_id] = {
            "cefr": cefr,
            "lessons_read": read,
            "lessons_total": total,
            "percentage": round(read / total * 100) if total > 0 else 0,
        }
    return result


def get_study_streak(user_id: int | None) -> dict:
    """Calculate study streak (consecutive days with any activity).

    Returns: {current_streak: int, best_streak: int, last_study_date: str|None}
    """
    from datetime import datetime, timedelta, timezone

    from models import VocabularyProgress

    # Collect all activity dates from LessonRead + VocabularyProgress
    dates: set = set()

    lr_query = LessonRead.query
    vp_query = VocabularyProgress.query

    if user_id is not None:
        lr_query = lr_query.filter_by(user_id=user_id)
        vp_query = vp_query.filter_by(user_id=user_id)
    else:
        lr_query = lr_query.filter(LessonRead.user_id.is_(None))
        vp_query = vp_query.filter(VocabularyProgress.user_id.is_(None))

    for r in lr_query.all():
        if r.read_at:
            dates.add(r.read_at.date())

    for v in vp_query.all():
        if v.last_reviewed:
            dates.add(v.last_reviewed.date())

    # Also try QuizAttempt if available
    try:
        from models import QuizAttempt
        qa_query = QuizAttempt.query
        if user_id is not None:
            qa_query = qa_query.filter_by(user_id=user_id)
        else:
            qa_query = qa_query.filter(QuizAttempt.user_id.is_(None))
        for q in qa_query.all():
            if q.attempted_at:
                dates.add(q.attempted_at.date())
    except (ImportError, Exception):
        pass

    if not dates:
        return {"current_streak": 0, "best_streak": 0, "last_study_date": None}

    sorted_dates = sorted(dates, reverse=True)
    last_study = sorted_dates[0]
    today = datetime.now(timezone.utc).date()

    # Current streak: consecutive days ending today or yesterday
    current = 0
    check_date = today
    if last_study < today - timedelta(days=1):
        current = 0  # Streak broken
    else:
        for d in sorted_dates:
            if d == check_date:
                current += 1
                check_date -= timedelta(days=1)
            elif d < check_date:
                break

    # Best streak
    best = 1
    streak = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] - timedelta(days=1):
            streak += 1
            best = max(best, streak)
        else:
            streak = 1

    return {
        "current_streak": current,
        "best_streak": max(best, current),
        "last_study_date": last_study.isoformat(),
    }
