import os
from flask import Flask


def create_app():
    app = Flask(__name__)

    # Config defaults
    app.config.from_mapping(
        SCHEDULER_CRON=os.getenv("SCHEDULER_CRON", "*/30 * * * *"),
        STORAGE_BACKEND=os.getenv("STORAGE_BACKEND", "mysql"),
        SQLITE_PATH=os.getenv("SQLITE_PATH", "/data/papers.db"),
        MAX_ITEMS_PER_RUN=int(os.getenv("MAX_ITEMS_PER_RUN", "50")),
        USER_AGENT=os.getenv("USER_AGENT", "LiteratureRetrieverBot/1.0 (+https://example.com)"),
        FEEDS=[s.strip() for s in os.getenv("FEEDS", "").split(",") if s.strip()],
        # MySQL config defaults
        MYSQL_HOST=os.getenv("MYSQL_HOST", "10.7.2.207"),
        MYSQL_PORT=int(os.getenv("MYSQL_PORT", "30211")),
        MYSQL_DB=os.getenv("MYSQL_DB", "ai4pv"),
        MYSQL_USER=os.getenv("MYSQL_USER", "share"),
        MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", 'u7!Y#%V&A!N%7e'),
    )

    # Register blueprints
    from .api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
