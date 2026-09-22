import asyncio
import json
import subprocess
from pathlib import Path

import websockets
from websockets.exceptions import ConnectionClosed


CONFIG_FILE = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "client.json"
)


EVENTS = {
    "WARDEN_ENTERED": (
        "🔴 Warden entered",
        "Heads up."
    ),
    "WARDEN_STOOD_UP": (
        "🟠 Warden stood up",
        "Eyes open."
    ),
    "WARDEN_LOOKING": (
        "🟡 Warden looking",
        "Be careful."
    ),
    "COAST_CLEAR": (
        "🟢 Coast clear",
        "You're good."
    ),
    "WARDEN_LEFT": (
        "🟢 Warden left",
        "Back to normal."
    ),
}


def load_config():
    with open(CONFIG_FILE, "r") as file:
        return json.load(file)


def notify(title, message):
    subprocess.run(
        [
            "notify-send",
            title,
            message,
        ],
        check=False,
    )


async def connect_and_listen(server, token):
    print("Connecting to Warden Watch...")

    async with websockets.connect(server) as websocket:

        await websocket.send(json.dumps({
            "type": "auth",
            "token": token
        }))

        response = json.loads(await websocket.recv())

        if not response.get("success"):
            print("Authentication failed.")
            print(response.get("reason", "Unknown reason"))
            return

        print("Authenticated as client.")
        print("Waiting for alerts...")

        async for message in websocket:
            data = json.loads(message)

            event = data.get("event")

            if event not in EVENTS:
                print(f"Unknown event: {event}")
                continue

            title, body = EVENTS[event]

            notify(title, body)


async def main():
    config = load_config()

    server = config["server"]
    token = config["client_token"]

    retry_delay = 1

    while True:
        try:
            await connect_and_listen(server, token)

            # If the connection ended normally, start retrying.
            print("Connection closed.")

        except (ConnectionClosed, OSError) as error:
            print(f"Connection lost: {error}")

        except Exception as error:
            print(f"Unexpected error: {error}")

        print(f"Reconnecting in {retry_delay} seconds...")

        await asyncio.sleep(retry_delay)

        retry_delay = min(retry_delay * 2, 30)


if __name__ == "__main__":
    asyncio.run(main())

