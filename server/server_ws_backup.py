import asyncio
import json
import secrets
from pathlib import Path

import websockets
from websockets.exceptions import ConnectionClosed


CONFIG_FILE = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "server.json"
)

MAX_CLIENTS = 100

ALLOWED_EVENTS = {
    "WARDEN_ENTERED",
    "WARDEN_STOOD_UP",
    "WARDEN_LOOKING",
    "COAST_CLEAR",
    "WARDEN_LEFT",
}

clients = set()
lookout = None


def load_config():
    with open(CONFIG_FILE, "r") as file:
        return json.load(file)


CONFIG = load_config()

CLIENT_TOKEN = CONFIG["client_token"]
LOOKOUT_TOKEN = CONFIG["lookout_token"]


def token_matches(provided, expected):
    if not isinstance(provided, str):
        return False

    return secrets.compare_digest(provided, expected)


async def send_json(websocket, data):
    await websocket.send(json.dumps(data))


async def authenticate(websocket):
    try:
        raw_message = await websocket.recv()
        data = json.loads(raw_message)

    except (json.JSONDecodeError, ConnectionClosed):
        return None

    if not isinstance(data, dict):
        return None

    if data.get("type") != "auth":
        await send_json(websocket, {
            "type": "auth_result",
            "success": False,
            "reason": "Authentication required"
        })
        return None

    token = data.get("token")

    # Lookout authentication
    if token_matches(token, LOOKOUT_TOKEN):

        global lookout

        if lookout is not None:
            await send_json(websocket, {
                "type": "auth_result",
                "success": False,
                "reason": "Lookout already connected"
            })
            return None

        lookout = websocket

        await send_json(websocket, {
            "type": "auth_result",
            "success": True,
            "role": "lookout"
        })

        print("[+] Lookout authenticated")

        return "lookout"

    # Client authentication
    if token_matches(token, CLIENT_TOKEN):

        if len(clients) >= MAX_CLIENTS:
            await send_json(websocket, {
                "type": "auth_result",
                "success": False,
                "reason": "Server client limit reached"
            })
            return None

        clients.add(websocket)

        await send_json(websocket, {
            "type": "auth_result",
            "success": True,
            "role": "client"
        })

        print(
            f"[+] Client authenticated "
            f"({len(clients)} total)"
        )

        return "client"

    await send_json(websocket, {
        "type": "auth_result",
        "success": False,
        "reason": "Invalid token"
    })

    return None


async def broadcast(message):
    if not clients:
        return

    dead = set()

    for client in clients:
        try:
            await client.send(message)

        except ConnectionClosed:
            dead.add(client)

    clients.difference_update(dead)


async def handle_message(websocket, role, raw_message):

    if role != "lookout":
        print("[!] Client attempted to send a message")
        return

    try:
        data = json.loads(raw_message)

    except json.JSONDecodeError:
        print("[!] Invalid JSON from lookout")
        return

    if not isinstance(data, dict):
        return

    if data.get("type") != "alert":
        return

    event = data.get("event")

    if event not in ALLOWED_EVENTS:
        print(f"[!] Rejected unknown event: {event}")
        return

    message = json.dumps({
        "type": "alert",
        "event": event
    })

    print(f"[ALERT] {event}")

    await broadcast(message)


async def handler(websocket):

    global lookout

    role = await authenticate(websocket)

    if role is None:
        await websocket.close()
        return

    try:

        async for raw_message in websocket:
            await handle_message(
                websocket,
                role,
                raw_message
            )

    except ConnectionClosed:
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


async def main():

    print("Warden Watch relay")
    print(f"Using config: {CONFIG_FILE}")
    print("Listening on 0.0.0.0:8765")
    print(f"Maximum clients: {MAX_CLIENTS}")

    async with websockets.serve(
        handler,
        "0.0.0.0",
        8765,
        max_size=1024,
        max_queue=16,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
