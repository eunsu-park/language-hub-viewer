"""SQLite FTS5 full-text search indexing for language course lessons."""
import re
import sqlite3
from pathlib import Path


def create_fts_table(db_path: Path):
    """Create or recreate the FTS5 search table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS search_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE search_fts USING fts5(
            language,
            content_type,
            topic,
            filename,
            title,
            content,
            tokenize='unicode61'
        )
    """)
    conn.commit()
    conn.close()


def build_search_index(content_dir: Path, db_path: Path, lang: str = "ko"):
    """Index lesson Markdown files from a content directory."""
    conn = sqlite3.connect(str(db_path))
    # Extract course name from path: content/<Course>/<lang>/ -> course is parent of lang dir
    course_name = content_dir.parent.name if content_dir.parent.name != "content" else ""

    for md_file in sorted(content_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        title = _extract_title(content)
        # Remove markdown formatting for search
        plain = _strip_markdown(content)

        conn.execute(
            "INSERT INTO search_fts (language, content_type, topic, filename, title, content) VALUES (?, ?, ?, ?, ?, ?)",
            (lang, "lesson", course_name, md_file.name, title, plain)
        )

    conn.commit()
    conn.close()


def search(db_path: Path, query: str, lang: str = "", topic: str = "",
           content_type: str = "", limit: int = 50) -> list[dict]:
    """Search the FTS index."""
    if not query or len(query.strip()) < 2:
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Build FTS query
    terms = query.strip().split()
    if len(terms) == 1:
        fts_query = f'"{terms[0]}"*'
    else:
        fts_query = " ".join(f'"{t}"*' for t in terms)

    sql = """
        SELECT topic, filename, title,
               snippet(search_fts, 5, '<mark>', '</mark>', '...', 50) as snippet,
               content_type
        FROM search_fts
        WHERE search_fts MATCH ?
    """
    params = [fts_query]

    if lang:
        sql += " AND language = ?"
        params.append(lang)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if content_type:
        sql += " AND content_type = ?"
        params.append(content_type)

    sql += f" ORDER BY rank LIMIT {limit}"

    try:
        rows = conn.execute(sql, params).fetchall()
        results = [dict(row) for row in rows]
    except sqlite3.OperationalError:
        results = []

    conn.close()
    return results


def _extract_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _strip_markdown(content: str) -> str:
    """Strip markdown formatting for plain text indexing."""
    text = re.sub(r"```[\s\S]*?```", "", content)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|.*\|", "", text)
    return text
