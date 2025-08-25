from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class Paper:
    title: str
    url: str
    doi: Optional[str]
    source: str  # e.g., 'nature'
    published_at: Optional[datetime]
    authors: Optional[List[str]]
    abstract: Optional[str]
    journal: Optional[str]
    extras: Optional[Dict]

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        return d
