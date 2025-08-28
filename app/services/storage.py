import os
import sqlite3
import json
from typing import List, Dict, Optional
from flask import Flask
from ..models.paper import Paper
try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:  # optional until mysql is used
    pymysql = None
    DictCursor = None

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


class MySQLStorage:
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        if pymysql is None:
            raise RuntimeError("PyMySQL is required for MySQL backend. Please install PyMySQL.")
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._init_db()

    def _connect(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            autocommit=False,
            cursorclass=DictCursor,
            charset="utf8mb4",
        )

    def _init_db(self):
        conn = self._connect()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS papers (
                      id BIGINT AUTO_INCREMENT PRIMARY KEY,
                      title VARCHAR(1024) NOT NULL,
                      url VARCHAR(2048) NOT NULL,
                      url_hash CHAR(64) GENERATED ALWAYS AS (sha2(url,256)) STORED,
                      doi VARCHAR(255) NULL,
                      source VARCHAR(64) NOT NULL,
                      published_at DATETIME NULL,
                      authors TEXT NULL,
                      abstract MEDIUMTEXT NULL,
                      journal VARCHAR(255) NULL,
                      extras TEXT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      UNIQUE KEY uniq_url_hash (url_hash),
                      INDEX idx_source_published (source, published_at),
                      INDEX idx_title (title(255))
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                    """
                )
                # Migration: ensure url_hash exists and is unique; drop old uniq_url if present
                cur.execute("SHOW COLUMNS FROM papers LIKE 'url_hash'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE papers ADD COLUMN url_hash CHAR(64) AS (sha2(url,256)) STORED")
                cur.execute("SHOW INDEX FROM papers WHERE Key_name='uniq_url'")
                if cur.fetchone():
                    cur.execute("ALTER TABLE papers DROP INDEX uniq_url")
                cur.execute("SHOW INDEX FROM papers WHERE Key_name='uniq_url_hash'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE papers ADD UNIQUE KEY uniq_url_hash (url_hash)")

    def upsert_papers(self, papers: List[Paper]) -> int:
        if not papers:
            return 0
        conn = self._connect()
        with conn:
            with conn.cursor() as cur:
                sql = (
                    """
                    INSERT INTO papers
                      (title, url, doi, source, published_at, authors, abstract, journal, extras)
                    VALUES
                      (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      title=VALUES(title),
                      doi=VALUES(doi),
                      source=VALUES(source),
                      published_at=VALUES(published_at),
                      authors=VALUES(authors),
                      abstract=VALUES(abstract),
                      journal=VALUES(journal),
                      extras=VALUES(extras)
                    """
                )
                for p in papers:
                    cur.execute(
                        sql,
                        (
                            p.title,
                            p.url,
                            p.doi,
                            p.source,
                            p.published_at.strftime("%Y-%m-%d %H:%M:%S") if p.published_at else None,
                            ", ".join(p.authors) if p.authors else None,
                            p.abstract,
                            p.journal,
                            json.dumps(p.extras) if p.extras else None,
                        ),
                    )
            conn.commit()
        return len(papers)

    def search_papers(self, query: str = "", source: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict:
        conn = self._connect()
        items: List[Dict] = []
        with conn:
            with conn.cursor() as cur:
                sql = "SELECT * FROM papers WHERE 1=1"
                params: List = []
                if query:
                    sql += " AND (title LIKE %s OR abstract LIKE %s OR authors LIKE %s)"
                    like = f"%{query}%"
                    params.extend([like, like, like])
                if source:
                    sql += " AND source = %s"
                    params.append(source)
                sql += " ORDER BY (published_at IS NULL), published_at DESC, id DESC LIMIT %s OFFSET %s"
                params.extend([int(limit), int(offset)])
                cur.execute(sql, params)
                rows = cur.fetchall()
                for r in rows:
                    if isinstance(r, dict):
                        items.append(r)
                    else:
                        try:
                            items.append(dict(r))
                        except Exception:
                            pass
        return {"items": items, "count": len(items), "offset": offset, "limit": limit}


def get_storage(app: Flask):
    backend = (app.config.get("STORAGE_BACKEND") or "sqlite").lower()
    if backend == "mysql":
        return MySQLStorage(
            host=app.config.get("MYSQL_HOST", "127.0.0.1"),
            port=int(app.config.get("MYSQL_PORT", 3306)),
            user=app.config.get("MYSQL_USER", "root"),
            password=app.config.get("MYSQL_PASSWORD", ""),
            database=app.config.get("MYSQL_DB", "test"),
        )
    # default to sqlite for local/dev
    return SQLiteStorage(app.config.get("SQLITE_PATH", "/data/papers.db"))


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
                        json.dumps(p.extras) if p.extras else None,
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
        # SQLite: push NULLs to end
        sql += " ORDER BY COALESCE(published_at, '' ) DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        items = []
        for r in rows:
            items.append({k: r[k] for k in r.keys()})
        return {"items": items, "count": len(items), "offset": offset, "limit": limit}
