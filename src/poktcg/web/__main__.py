"""Entry point for `python -m poktcg.web`."""

import uvicorn

from poktcg.web.app import app

uvicorn.run(app, host="0.0.0.0", port=8000)
