import json
import os
import secrets
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "server.json"
WEB_DIR = BASE_DIR / "web"

MAX_CLIENTS = 100

ALLOWED_EVENTS = {
    "WARDEN_ENTERED",
    "WARDEN_STOOD_UP",
    "WARDEN_LOOKING",
    "COAST_CLEAR",
    "WARDEN_LEFT",
}


def load_config():
    """
    Use environment variables in production.
    Fall back to config/server.json for local development.
    """

    client_token = os.getenv("WARDEN_CLIENT_TOKEN")
    lookout_token = os.getenv("WARDEN_LOOKOUT_TOKEN")

    if client_token and lookout_token:
        return {
            "client_token": client_token,
            "lookout_token": lookout_token,
        }

    with open(CONFIG_FILE, "r") as file:
        return json.load(file)


CONFIG = load_config()

CLIENT_TOKEN = CONFIG["client_token"]
LOOKOUT_TOKEN = CONFIG["lookout_token"]

app = FastAPI(title="Warden Watch")

clients = set()
lookout = None


def token_matches(provided, expected):
    if not isinstance(provided, str):
        return False

    return secrets.compare_digest(provided, expected)


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

async def send_json(websocket, data):
    await websocket.send_text(json.dumps(data))


async def authenticate(websocket):
    global lookout

    try:
        raw_message = await websocket.receive_text()
        data = json.loads(raw_message)

    except (json.JSONDecodeError, WebSocketDisconnect):
        return None

    if not isinstance(data, dict):
        return None

    if data.get("type") != "auth":
        await send_json(websocket, {
            "type": "auth_result",
            "success": False,
            "reason": "Authentication required",
        })
        return None

    token = data.get("token")

    if token_matches(token, LOOKOUT_TOKEN):

        if lookout is not None:
            await send_json(websocket, {
                "type": "auth_result",
                "success": False,
                "reason": "Lookout already connected",
            })
            return None

        lookout = websocket

        await send_json(websocket, {
            "type": "auth_result",
            "success": True,
            "role": "lookout",
        })

        print("[+] Lookout authenticated")

        return "lookout"

    if token_matches(token, CLIENT_TOKEN):

        if len(clients) >= MAX_CLIENTS:
            await send_json(websocket, {
                "type": "auth_result",
                "success": False,
                "reason": "Server client limit reached",
            })
            return None

        clients.add(websocket)

        await send_json(websocket, {
            "type": "auth_result",
            "success": True,
            "role": "client",
        })

        print(
            f"[+] Client authenticated "
            f"({len(clients)} total)"
        )

        return "client"

    await send_json(websocket, {
        "type": "auth_result",
        "success": False,
        "reason": "Invalid token",
    })

    return None


async def broadcast(message):
    if not clients:
        return

    dead = set()

    for client in clients:
        try:
            await client.send_text(message)

        except Exception:
            dead.add(client)

    clients.difference_update(dead)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    global lookout

    await websocket.accept()

    role = await authenticate(websocket)

    if role is None:
        await websocket.close()
        return

    try:

        while True:
            raw_message = await websocket.receive_text()

            if role != "lookout":
                print("[!] Client attempted to send a message")
                continue

            try:
                data = json.loads(raw_message)

            except json.JSONDecodeError:
                print("[!] Invalid JSON from lookout")
                continue

            if not isinstance(data, dict):
                continue

            if data.get("type") != "alert":
                continue

            event = data.get("event")

            if event not in ALLOWED_EVENTS:
                print(f"[!] Rejected unknown event: {event}")
                continue

            message = json.dumps({
                "type": "alert",
                "event": event,
            })

            print(f"[ALERT] {event}")

            await broadcast(message)

    except WebSocketDisconnect:

        pass

    finally:

        clients.discard(websocket)

        if websocket is lookout:
            lookout = None
            print("[-] Lookout disconnected")

        elif role == "client":
            print(
                f"[-] Client disconnected "
                f"({len(clients)} total)"
            )


if __name__ == "__main__":
    uvicorn.run(
    app,
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)
