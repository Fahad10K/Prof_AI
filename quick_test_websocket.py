#!/usr/bin/env python3
"""
Quick WebSocket Test - Minimal test to verify WebSocket server is working
"""

import asyncio
import websockets
import json
import sys

async def test_websocket_connection():
    """Test basic WebSocket connection and ping."""
    uri = "ws://localhost:8765"
    
    try:
        print(f"🔗 Connecting to {uri}...")
        
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            
            # Wait for connection ready message
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"📨 Server response: {data.get('message', 'Connected')}")
                print(f"   Services: {data.get('services', {})}")
            except asyncio.TimeoutError:
                print("⏰ No initial message received (this is okay)")
            
            # Send ping
            print("📤 Sending ping...")
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Wait for pong
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                if data.get("type") == "pong":
                    print("✅ Ping/pong successful!")
                    print(f"   Response: {data.get('message', 'pong')}")
                    return True
                else:
                    print(f"❓ Unexpected response: {data}")
                    return False
            except asyncio.TimeoutError:
                print("⏰ Ping timeout - server may not be responding")
                return False
                
    except ConnectionRefusedError:
        print("❌ Connection refused - WebSocket server is not running")
        print("💡 Start the server with: python run_profai_websocket.py")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

async def main():
    """Main test function."""
    print("🧪 Quick WebSocket Connection Test")
    print("=" * 40)
    
    success = await test_websocket_connection()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 WebSocket server is working correctly!")
        print("🌐 You can now test in browser at:")
        print("   http://localhost:5001/profai-websocket-test")
    else:
        print("❌ WebSocket test failed")
        print("🔧 Troubleshooting:")
        print("   1. Make sure the server is running: python run_profai_websocket.py")
        print("   2. Check if port 8765 is available")
        print("   3. Verify no firewall is blocking the connection")
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test error: {e}")
        sys.exit(1)