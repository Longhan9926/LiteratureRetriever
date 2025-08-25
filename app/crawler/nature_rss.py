from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from ..models.paper import Paper


class NatureRSSCrawler:
    """
    Generic RSS crawler for Nature Portfolio journals.
    Provide RSS feed URLs via env FEEDS (comma-separated).
    """

    def __init__(self, feeds: List[str], user_agent: Optional[str] = None):
        self.feeds = feeds
        self.session = requests.Session()
        if user_agent:
            self.session.headers["User-Agent"] = user_agent
        self.session.headers.setdefault("Accept-Language", "en-US,en;q=0.9")

    def fetch_latest(self, max_items: int = 100) -> List[Paper]:
        all_papers: List[Paper] = []
        for feed in self.feeds:
            try:
                r = self.session.get(feed, timeout=20)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "xml")
                items = soup.select("item")[:max_items]
                for it in items:
                    title = it.title.get_text(strip=True) if it.title else None
                    link = it.link.get_text(strip=True) if it.link else None
                    pub_date = None
                    if it.pubDate and it.pubDate.string:
                        try:
                            pub_date = datetime.strptime(it.pubDate.string.strip(), "%a, %d %b %Y %H:%M:%S %Z")
                        except Exception:
                            pub_date = None
                    journal = urlparse(link).netloc if link else None
                    abstract, doi = self._fetch_detail(link)
                    if title and link:
                        all_papers.append(Paper(
                            title=title,
                            url=link,
                            doi=doi,
                            source="nature-portfolio",
                            published_at=pub_date,
                            authors=None,
                            abstract=abstract,
                            journal=journal,
                            extras={"feed": feed},
                        ))
            except Exception:
                continue
        return all_papers

    def _fetch_detail(self, url: Optional[str]):
        if not url:
            return None, None
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            abs_el = soup.select_one("div#Abs1-content, section#Abs1, section#Abs2")
            abstract = abs_el.get_text(" ", strip=True) if abs_el else None
            doi = None
            doi_el = soup.find("a", href=True, string=lambda x: isinstance(x, str) and x.startswith("https://doi.org/"))
            if doi_el:
                doi = doi_el.get_text(strip=True).replace("https://doi.org/", "")
            return abstract, doi
        except Exception:
            return None, None
