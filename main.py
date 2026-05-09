import asyncio
import os
import websockets

rooms = {}        # room_code -> { ws, event, peer }
active_keys = {}  # license_key -> ws  (one connection per license key)

async def handler(ws):
    code = None
    license_key = None
    try:
        first = await ws.recv()
        if isinstance(first, bytes):
            first = first.decode("utf-8")
        first = first.strip()

        # Format: "<KEY>:<ROOM>" (preferred) or just "<ROOM>" (backward compat)
        if ":" in first:
            license_key, code = first.split(":", 1)
            license_key = license_key.strip()
            code = code.strip()
        else:
            code = first

        # Concurrent session detection: kick previous holder of same key
        if license_key:
            old = active_keys.get(license_key)
            if old is not None and old is not ws:
                print(f"[{license_key[:8]}...] Kicking previous session", flush=True)
                try:
                    await old.send("KICKED")
                    await old.close()
                except Exception:
                    pass
            active_keys[license_key] = ws

        print(f"[{code}] Client joined", flush=True)

        if code in rooms:
            room = rooms.pop(code)
            peer_ws = room["ws"]
            print(f"[{code}] Room matched!", flush=True)
            await peer_ws.send("OK")
            await ws.send("OK")
            room["peer"] = ws
            room["event"].set()
            try:
                async for msg in ws:
                    await peer_ws.send(msg)
            except websockets.ConnectionClosed:
                pass
            finally:
                try: await peer_ws.close()
                except: pass
                print(f"[{code}] Session ended", flush=True)
        else:
            event = asyncio.Event()
            room = {"ws": ws, "event": event, "peer": None}
            rooms[code] = room
            await ws.send("WAIT")
            print(f"[{code}] Waiting for peer...", flush=True)
            try:
                await asyncio.wait_for(event.wait(), timeout=300)
            except asyncio.TimeoutError:
                rooms.pop(code, None)
                print(f"[{code}] Room expired", flush=True)
                return
            peer_ws = room["peer"]
            if peer_ws is None: return
            try:
                async for msg in ws:
                    await peer_ws.send(msg)
            except websockets.ConnectionClosed:
                pass
            finally:
                try: await peer_ws.close()
                except: pass
                print(f"[{code}] Session ended", flush=True)
    except websockets.ConnectionClosed:
        if code and code in rooms: rooms.pop(code, None)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        if code and code in rooms: rooms.pop(code, None)
    finally:
        # Free the license key only if THIS ws still holds it
        if license_key and active_keys.get(license_key) is ws:
            active_keys.pop(license_key, None)

async def main():
    port = int(os.environ.get("PORT", 8080))
    print("=== ### Relay Server ===", flush=True)
    print(f"Listening on port {port}", flush=True)
    async with websockets.serve(handler, "0.0.0.0", port, max_size=6*1024*1024):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
