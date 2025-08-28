#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from typing import Any

# Allow running from repo root
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.crawler.nature import NatureCrawler  # noqa: E402


def default_user_agent() -> str:
    return os.getenv("USER_AGENT", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0")


def paper_to_primitive(p: Any) -> dict:
    # p is app.models.paper.Paper
    d = {
        "title": getattr(p, "title", None),
        "url": getattr(p, "url", None),
        "doi": getattr(p, "doi", None),
        "source": getattr(p, "source", None),
        "published_at": None,
        "authors": getattr(p, "authors", None),
        "abstract": getattr(p, "abstract", None),
        "journal": getattr(p, "journal", None),
    }
    pub = getattr(p, "published_at", None)
    if isinstance(pub, datetime):
        d["published_at"] = pub.isoformat()
    return d


def main():
    parser = argparse.ArgumentParser(description="Test Nature crawler")
    parser.add_argument("--max-items", type=int, default=5, help="Max items to fetch")
    parser.add_argument("--user-agent", type=str, default=default_user_agent(), help="User-Agent header")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    crawler = NatureCrawler(user_agent=args.user_agent)
    papers = crawler.fetch_latest(max_items=args.max_items)

    if args.json:
        print(json.dumps([paper_to_primitive(p) for p in papers], ensure_ascii=False, indent=2))
    else:
        print(f"Fetched {len(papers)} items:")
        for i, p in enumerate(papers, 1):
            pub_val = getattr(p, 'published_at', None)
            pub = pub_val.isoformat() if isinstance(pub_val, datetime) else "-"
            authors = ", ".join(p.authors) if p.authors else "-"
            print(f"{i}. {p.title}\n   url: {p.url}\n   doi: {p.doi or '-'}\n   date: {pub}\n   authors: {authors}\n")


if __name__ == "__main__":
    main()
