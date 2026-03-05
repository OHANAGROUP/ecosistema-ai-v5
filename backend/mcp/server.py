import asyncio
import websockets
import json
import logging

class MCPServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.connections = set()

    async def handler(self, websocket, path):
        self.connections.add(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                # Lógica de JSON-RPC 2.0 para NotebookLM y cross-agent
                response = {"status": "received", "echo": data}
                await websocket.send(json.dumps(response))
        finally:
            self.connections.remove(websocket)

    async def start(self):
        async with websockets.serve(self.handler, self.host, self.port):
            logging.info(f"MCP Server iniciado en ws://{self.host}:{self.port}")
            await asyncio.Future()  # run forever

if __name__ == "__main__":
    server = MCPServer()
    asyncio.run(server.start())
