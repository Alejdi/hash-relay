import asyncio
import websockets

rooms = {}

async def handler(ws):
    code = None
    try:
        code = await ws.recv()
        if isinstance(code, bytes):
            code = code.decode("utf-8")
        code = code.strip()
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

async def main():
    port = 8080
    print("=== ### Relay Server ===", flush=True)
    print(f"Listening on port {port}", flush=True)
    async with websockets.serve(handler, "0.0.0.0", port, max_size=65536):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
