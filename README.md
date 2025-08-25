# LiteratureRetriever

A minimal Flask service that periodically crawls latest Nature research articles and stores them to SQLite. Exposes simple APIs to query papers and to trigger crawling.

## Features
- Scheduled crawler (polling interval derived from cron like `*/30 * * * *`)
- Nature latest articles scraping: title, url, DOI, authors, date, abstract
- SQLite storage with upsert semantics
- REST API: health, list papers, trigger crawl, crawl status
- Dockerized with Gunicorn

## API
- `GET /api/health` – service health
- `GET /api/papers?q=keyword&source=nature&limit=50&offset=0`
- `POST /api/crawl/run` – run the crawler immediately
- `GET /api/crawl/status` – last run info

## Run locally with uv
```bash
# Optional: choose mirror by editing pyproject [[tool.uv.index]]
# Run the app (scheduler disabled in foreground)
START_SCHEDULER=0 SQLITE_PATH=$(pwd)/data/papers.db uv run -- python -m app.wsgi
# Or run via gunicorn
START_SCHEDULER=1 SQLITE_PATH=$(pwd)/data/papers.db uv run -- gunicorn -w 2 -b 0.0.0.0:8000 app.wsgi:app
```
Open http://127.0.0.1:8000/api/health

## Docker
Classic pip-based Dockerfile:
```bash
docker build -t literature-retriever -f Dockerfile .
mkdir -p data
docker run -d --name lr -p 8000:8000 \
  -e SCHEDULER_CRON="*/30 * * * *" -e MAX_ITEMS_PER_RUN=30 \
  -e USER_AGENT="LiteratureRetrieverBot/1.0" \
  -v $(pwd)/data:/data literature-retriever
```

uv-based Dockerfile:
```bash
docker build -t literature-retriever-uv -f Dockerfile.uv .
docker run -d --name lr-uv -p 8000:8000 \
  -e SCHEDULER_CRON="*/30 * * * *" -e MAX_ITEMS_PER_RUN=30 \
  -e USER_AGENT="LiteratureRetrieverBot/1.0" \
  -v $(pwd)/data:/data literature-retriever-uv
```

## Config via env
- `SQLITE_PATH` (default `/data/papers.db`)
- `SCHEDULER_CRON` (default `*/30 * * * *`)
- `MAX_ITEMS_PER_RUN` (default `50`)
- `USER_AGENT` (default `LiteratureRetrieverBot/1.0`)
- `FEEDS` (comma-separated RSS feed URLs for Nature Portfolio)
- `START_SCHEDULER` (1 to auto-start, 0 to disable)

## Notes
- Respect Nature's robots.txt and terms. Keep frequency low, add a contact in UA.
- To add more sources, implement new crawlers in `app/crawler/` and extend the scheduler.
