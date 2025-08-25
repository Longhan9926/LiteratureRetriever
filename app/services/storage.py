import os
import sqlite3
from typing import List, Dict, Optional
from flask import Flask
from ..models.paper import Paper

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  doi TEXT,
  source TEXT NOT NULL,
  published_at TEXT,
  authors TEXT,
  abstract TEXT,
  journal TEXT,
  extras TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_papers_source_published ON papers(source, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);
"""


def get_db(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str):
    conn = get_db(path)
    with conn:
        conn.executescript(SCHEMA)
    conn.close()


class SQLiteStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(db_path)

    def upsert_papers(self, papers: List[Paper]) -> int:
        if not papers:
            return 0
        conn = get_db(self.db_path)
        with conn:
            for p in papers:
                conn.execute(
                    """
                    INSERT INTO papers(title, url, doi, source, published_at, authors, abstract, journal, extras)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title,
                        doi=excluded.doi,
                        source=excluded.source,
                        published_at=excluded.published_at,
                        authors=excluded.authors,
                        abstract=excluded.abstract,
                        journal=excluded.journal,
                        extras=excluded.extras
                    """,
                    (
                        p.title,
                        p.url,
                        p.doi,
                        p.source,
                        p.published_at.isoformat() if p.published_at else None,
                        ", ".join(p.authors) if p.authors else None,
                        p.abstract,
                        p.journal,
                        str(p.extras) if p.extras else None,
                    ),
                )
        conn.close()
        return len(papers)

    def search_papers(self, query: str = "", source: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict:
        conn = get_db(self.db_path)
        sql = "SELECT * FROM papers WHERE 1=1"
        params: List = []
        if query:
            sql += " AND (title LIKE ? OR abstract LIKE ? OR authors LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like, like])
        if source:
            sql += " AND source = ?"
            params.append(source)
        # SQLite doesn't support NULLS LAST; use COALESCE to push NULLs to the end
        sql += " ORDER BY COALESCE(published_at, '' ) DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        items = []
        for r in rows:
            items.append({k: r[k] for k in r.keys()})
        return {"items": items, "count": len(items), "offset": offset, "limit": limit}


def get_storage(app: Flask) -> SQLiteStorage:
    backend = app.config.get("STORAGE_BACKEND", "sqlite")
    if backend != "sqlite":
        raise NotImplementedError("Only sqlite backend implemented for now")
    return SQLiteStorage(app.config.get("SQLITE_PATH", "/data/papers.db"))
