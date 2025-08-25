import os
from . import create_app
from .utils.logging import setup_logging

logger = setup_logging()
app = create_app()

# Optionally start scheduler on import; controlled via env START_SCHEDULER (default: 1)
if os.getenv("START_SCHEDULER", "1") == "1":
    from .services.scheduler import get_scheduler  # noqa: E402
    get_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
