#!/usr/bin/env python3
"""
Simple WebSocket Server - Minimal WebSocket server for testing
"""

import asyncio
import websockets
import json
import time
from datetime import datetime

def log(*args):
    """Simple logging"""
    timestamp = datetime.utcnow().isoformat(sep=' ', timespec='milliseconds') + 'Z'
    print(f"[{timestamp}][SimpleWS]", *args, flush=True)

async def simple_handler(websocket):
    """Simple WebSocket handler for testing."""
    client_id = f"simple_client_{int(time.time())}"
    log(f"Client connected: {client_id}")
    
    try:
        # Send connection ready
        await websocket.send(json.dumps({
            "type": "connection_ready",
            "message": "Simple WebSocket server connected",
            "client_id": client_id,
            "services": {
                "chat": False,
                "audio": False,
                "teaching": False
            },
            "mode": "simple_test"
        }))
        
        # Handle messages
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type", "unknown")
                
                log(f"Received {message_type} from {client_id}")
                
                if message_type == "ping":
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "message": "Simple server pong",
                        "server_time": time.time(),
                        "client_id": client_id
                    }))
                elif message_type == "echo":
                    await websocket.send(json.dumps({
                        "type": "echo_response",
                        "original_message": data,
                        "server_time": time.time(),
                        "client_id": client_id
                    }))
                else:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": f"Simple server doesn't support: {message_type}",
                        "supported_types": ["ping", "echo"],
                        "client_id": client_id
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": "Invalid JSON",
                    "client_id": client_id
                }))
            except Exception as e:
                log(f"Error processing message from {client_id}: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": f"Processing error: {str(e)}",
                    "client_id": client_id
                }))
                
    except websockets.exceptions.ConnectionClosed:
        log(f"Client {client_id} disconnected")
    except Exception as e:
        log(f"Handler error for {client_id}: {e}")

async def start_simple_server(host="0.0.0.0", port=8766):
    """Start simple WebSocket server."""
    log(f"Starting simple WebSocket server on {host}:{port}")
    
    try:
        async with websockets.serve(simple_handler, host, port):
            log(f"✅ Simple WebSocket server running at ws://{host}:{port}")
            log("Supported message types: ping, echo")
            log("Test with: python test_basic_websocket.py")
            await asyncio.Future()  # Run forever
    except OSError as e:
        if "Address already in use" in str(e):
            log(f"❌ Port {port} is already in use!")
            log("💡 Stop the existing server or use a different port")
        else:
            log(f"❌ Failed to start server: {e}")
        raise
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(start_simple_server())
    except KeyboardInterrupt:
        log("🛑 Simple server shutting down")
    except Exception as e:
        log(f"💥 Server error: {e}")
        exit(1)