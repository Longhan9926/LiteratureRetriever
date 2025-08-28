import json
from datetime import datetime
from typing import List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from ..models.paper import Paper


BASE_URL = "https://www.nature.com"
LATEST_URL = "https://www.nature.com/nature/research-articles"  # Research Articles
SEARCH_URL = "https://www.nature.com/search"


class NatureCrawler:
    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        if user_agent:
            self.session.headers["User-Agent"] = user_agent
        self.session.headers.setdefault("Accept-Language", "en-US,en;q=0.9")

    def fetch_latest(self, max_items: int = 50) -> List[Paper]:
        resp = self.session.get(LATEST_URL, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article.c-card")
        papers: List[Paper] = []
        for card in cards[:max_items]:
            title_el = card.select_one("h3 a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href_val = title_el.get("href")
            if isinstance(href_val, list):
                href = href_val[0] if href_val else ""
            else:
                href = href_val or ""
            url = href if (isinstance(href, str) and href.startswith("http")) else f"{BASE_URL}{href}"
            journal = "Nature"
            # Date
            date_el = card.select_one("time")
            published_at = None
            if date_el and hasattr(date_el, "attrs") and date_el.has_attr("datetime"):
                try:
                    dtval = date_el.get("datetime")
                    if isinstance(dtval, str):
                        published_at = datetime.fromisoformat(dtval.replace("Z", "+00:00"))
                except Exception:
                    published_at = None
            # Author list
            authors = [a.get_text(strip=True) for a in card.select("ul.c-author-list li")]
            # Abstract not on listing; fetch detail for richer info
            abstract, doi = self._fetch_detail(url)
            papers.append(Paper(
                title=title,
                url=url,
                doi=doi,
                source="nature",
                published_at=published_at,
                authors=authors or None,
                abstract=abstract,
                journal=journal,
                extras=None,
            ))
        return papers

    def fetch_search(self, query: str, max_items: int = 50) -> List[Paper]:
        params = {
            "q": query,
            "journal": "nature",
            "article_type": "research",
            "order": "date_desc",
        }
        r = self.session.get(SEARCH_URL, params=params, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        papers: List[Paper] = []
        # Try card layout first
        items = soup.select("article.c-card")
        if not items:
            # Fallback to older list layout
            items = soup.select("li.app-article-list-row__item, li.mb20")
        for el in items[:max_items]:
            a_tag = el.select_one("h3 a, a.c-card__link") or el.find("a", href=True)
            if not a_tag or not isinstance(a_tag, Tag):
                continue
            title = a_tag.get_text(strip=True)
            href_val = a_tag.get("href")
            href = href_val[0] if isinstance(href_val, list) and href_val else (href_val or "")
            url = href if (isinstance(href, str) and href.startswith("http")) else f"{BASE_URL}{href}"
            # Date (if available)
            published_at = None
            t = el.find("time")
            if isinstance(t, Tag) and t.has_attr("datetime"):
                try:
                    dtv = t.get("datetime")
                    if isinstance(dtv, str):
                        published_at = datetime.fromisoformat(dtv.replace("Z", "+00:00"))
                except Exception:
                    published_at = None
            # Authors (best effort)
            authors = [a.get_text(strip=True) for a in el.select("ul.c-author-list li")] or None
            abstract, doi = self._fetch_detail(url)
            papers.append(Paper(
                title=title,
                url=url,
                doi=doi,
                source="nature",
                published_at=published_at,
                authors=authors,
                abstract=abstract,
                journal="Nature",
                extras={"query": query},
            ))
        return papers

    def _fetch_detail(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            # Abstract
            abs_el = soup.select_one("div#Abs1-content, section#Abs1")
            abstract = abs_el.get_text(" ", strip=True) if abs_el else None
            # DOI
            doi = None
            doi_meta = soup.find("meta", attrs={"name": "dc.identifier"})
            content = None
            if isinstance(doi_meta, Tag):
                content = doi_meta.get("content")
                if isinstance(content, str) and content.startswith("doi:"):
                    doi = content[4:]
            return abstract, doi
        except Exception:
            return None, None
