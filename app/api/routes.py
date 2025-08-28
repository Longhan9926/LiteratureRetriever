from flask import Blueprint, jsonify, request, current_app
from ..services.storage import get_storage
from ..services.scheduler import get_scheduler

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.get("/papers")
def list_papers():
    storage = get_storage(current_app)
    q = request.args.get("q", "").strip()
    source = request.args.get("source")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    return jsonify(storage.search_papers(query=q, source=source, limit=limit, offset=offset))


@api_bp.post("/crawl/run")
def trigger_crawl():
    scheduler = get_scheduler(current_app)
    sync = request.args.get("sync", "0") == "1"
    if sync:
        ran = scheduler.run_once()
        return jsonify({"triggered": True, "items": ran, "mode": "sync"})
    else:
        started = scheduler.run_once_async()
        return jsonify({"triggered": started, "mode": "async"})


@api_bp.get("/crawl/status")
def crawl_status():
    scheduler = get_scheduler(current_app)
    return jsonify(scheduler.status())
