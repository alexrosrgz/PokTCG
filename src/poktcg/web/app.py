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
from poktcg.web.runner import run_battleground, run_optimization

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PokTCG Deck Optimizer")

# Mount the static directory to serve assets like favicons securely 
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Single-run lock
_running = False
_run_lock = threading.Lock()

DECKS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "decks"
SAVED_DECKS_FILE = DECKS_DIR / "saved_decks.json"

def _ensure_decks_file():
    if not DECKS_DIR.exists():
        DECKS_DIR.mkdir(parents=True)
    if not SAVED_DECKS_FILE.exists():
        SAVED_DECKS_FILE.write_text("{}")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/api/saved_decks")
async def get_saved_decks():
    _ensure_decks_file()
    try:
        return json.loads(SAVED_DECKS_FILE.read_text())
    except Exception:
        return {}


@app.post("/api/saved_decks")
async def save_deck(request: Request):
    _ensure_decks_file()
    body = await request.json()
    name = body.get("name")
    if not name:
        return {"error": "Name is required"}
    try:
        data = json.loads(SAVED_DECKS_FILE.read_text())
    except Exception:
        data = {}
    data[name] = body.get("deck")
    SAVED_DECKS_FILE.write_text(json.dumps(data, indent=2))
    return {"success": True}


@app.delete("/api/saved_decks/{name}")
async def delete_saved_deck(name: str):
    _ensure_decks_file()
    try:
        data = json.loads(SAVED_DECKS_FILE.read_text())
        if name in data:
            del data[name]
            SAVED_DECKS_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
    return {"success": True}


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


@app.post("/api/battleground")
async def battleground(request: Request):
    global _running

    with _run_lock:
        if _running:
            return StreamingResponse(
                _error_stream("An optimization or battleground run is already running. Please wait."),
                media_type="text/event-stream",
            )
        _running = True

    body = await request.json()
    mode = body.get("mode", "all_vs_all")
    rounds = body.get("rounds", 20)
    deck_names = body.get("deck_names", [])
    primary_deck = body.get("primary_deck")
    opponent_names = body.get("opponent_names", [])

    queue: Queue = Queue()

    def progress_callback(event_type: str, data: dict) -> None:
        queue.put((event_type, data))

    def run_in_thread():
        global _running
        try:
            result = run_battleground(
                mode=mode,
                rounds=rounds,
                deck_names=deck_names,
                primary_deck=primary_deck,
                opponent_names=opponent_names,
                progress_callback=progress_callback,
                num_workers=max(1, (mp.cpu_count() or 2) - 2),
            )
            queue.put(("complete", result))
        except Exception as e:
            queue.put(("error", {"message": str(e)}))
        finally:
            queue.put(None)
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
