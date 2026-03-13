"""FastAPI web application for PokTCG deck optimizer."""

from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
import threading
from pathlib import Path
from queue import Empty, Queue

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from poktcg.cards.card_db import get_card_db
from poktcg.web.runner import run_optimization

app = FastAPI(title="PokTCG Deck Optimizer")

# Single-run lock
_running = False
_run_lock = threading.Lock()

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/api/cards")
async def get_cards():
    db = get_card_db()
    cards = []
    for card in db.cards.values():
        cards.append({
            "id": card.id,
            "name": card.name,
            "supertype": card.supertype,
            "subtypes": card.subtypes,
            "hp": card.hp,
            "types": card.types,
            "set_id": card.set_id,
        })
    return {"cards": cards, "total": len(cards)}


@app.post("/api/optimize")
async def optimize(request: Request):
    global _running

    with _run_lock:
        if _running:
            return StreamingResponse(
                _error_stream("An optimization is already running. Please wait."),
                media_type="text/event-stream",
            )
        _running = True

    body = await request.json()
    archetypes = body.get("archetypes", [])
    mode = body.get("mode", "coevolution")
    counter_targets = body.get("counter_targets", [])
    depth = body.get("depth", "normal")
    card_pool = body.get("card_pool", "all")

    queue: Queue = Queue()

    def progress_callback(event_type: str, data: dict) -> None:
        queue.put((event_type, data))

    def run_in_thread():
        global _running
        try:
            result = run_optimization(
                archetypes=archetypes,
                mode=mode,
                counter_targets=counter_targets,
                depth=depth,
                card_pool=card_pool,
                progress_callback=progress_callback,
                num_workers=max(1, (mp.cpu_count() or 2) - 2),
            )
            queue.put(("complete", result))
        except Exception as e:
            queue.put(("error", {"message": str(e)}))
        finally:
            queue.put(None)  # Sentinel
            with _run_lock:
                _running = False

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    return StreamingResponse(
        _event_stream(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_stream(queue: Queue):
    while True:
        try:
            item = queue.get_nowait()
        except Empty:
            await asyncio.sleep(0.1)
            continue

        if item is None:
            break

        event_type, data = item
        yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _error_stream(message: str):
    yield f"event: error\ndata: {json.dumps({'message': message})}\n\n"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
