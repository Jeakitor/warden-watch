import asyncio
import json
from pathlib import Path

import websockets
from websockets.exceptions import ConnectionClosed


CONFIG_FILE = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "lookout.json"
)


EVENTS = {
    "1": "WARDEN_ENTERED",
    "2": "WARDEN_STOOD_UP",
    "3": "WARDEN_LOOKING",
    "4": "COAST_CLEAR",
    "5": "WARDEN_LEFT",
}


def load_config():
    with open(CONFIG_FILE, "r") as file:
        return json.load(file)


async def connect(server, token):
    print("Connecting to Warden Watch...")

    websocket = await websockets.connect(server)

    await websocket.send(json.dumps({
        "type": "auth",
        "token": token
    }))

    response = json.loads(await websocket.recv())

    if not response.get("success"):
        await websocket.close()

        raise RuntimeError(
            response.get("reason", "Authentication failed")
        )

    print("Authenticated as LOOKOUT.")

    return websocket


async def main():
    config = load_config()

    server = config["server"]
    token = config["lookout_token"]

    retry_delay = 1

    print()
    print("╔══════════════════════════════╗")
    print("║       WARDEN WATCH           ║")
    print("╚══════════════════════════════╝")
    print()
    print("[1] Warden entered")
    print("[2] Warden stood up")
    print("[3] Warden looking")
    print("[4] Coast clear")
    print("[5] Warden left")
    print("[q] Quit")
    print()

    websocket = None

    while True:

        # Establish a connection if we don't have one.
        if websocket is None:

            try:
                websocket = await connect(server, token)
                retry_delay = 1

            except (ConnectionClosed, OSError, RuntimeError) as error:
                print(f"Connection failed: {error}")
                print(
                    f"Retrying in {retry_delay} seconds..."
                )

                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)

                continue

        try:
            choice = await asyncio.to_thread(
                input,
                "> "
            )

            if choice == "q":
                await websocket.close()
                break

            if choice not in EVENTS:
                print("Unknown command.")
                continue

            message = {
                "type": "alert",
                "event": EVENTS[choice],
            }

            await websocket.send(
                json.dumps(message)
            )

            print(f"Sent: {EVENTS[choice]}")

        except (
            ConnectionClosed,
            ConnectionResetError,
            BrokenPipeError,
            OSError
        ) as error:

            print(f"Connection lost: {error}")

            try:
                await websocket.close()
            except Exception:
                pass

            websocket = None

            print("The lookout will reconnect automatically.")


if __name__ == "__main__":
    asyncio.run(main())
