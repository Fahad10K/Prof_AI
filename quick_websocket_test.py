#!/usr/bin/env python3
"""
Quick WebSocket connection test - minimal dependencies
"""

import asyncio
import websockets
import json

async def test_simple_websocket():
    """Test the simple WebSocket endpoint."""
    uri = "ws://localhost:5001/ws/test"
    
    try:
        print(f"🔗 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to simple WebSocket!")
            
            # Wait for connection ready message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Server says: {data}")
            
            # Send ping
            print("📤 Sending ping...")
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Get response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Ping response: {data}")
            
            print("✅ Simple WebSocket test PASSED!")
            return True
            
    except Exception as e:
        print(f"❌ Simple WebSocket test FAILED: {e}")
        return False

async def test_audio_websocket():
    """Test the audio WebSocket endpoint."""
    uri = "ws://localhost:5001/ws/audio-stream"
    
    try:
        print(f"🔗 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to audio WebSocket!")
            
            # Wait for connection ready message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Server says: {data}")
            print(f"   Services available: {data.get('services_available')}")
            print(f"   Chat service: {data.get('chat_service')}")
            print(f"   Audio service: {data.get('audio_service')}")
            
            # Send ping
            print("📤 Sending ping...")
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Get response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Ping response: {data}")
            
            print("✅ Audio WebSocket connection test PASSED!")
            return True
            
    except Exception as e:
        print(f"❌ Audio WebSocket test FAILED: {e}")
        return False

async def main():
    """Run all WebSocket tests."""
    print("🧪 Quick WebSocket Connection Test")
    print("=" * 40)
    
    # Test simple WebSocket first
    simple_ok = await test_simple_websocket()
    print()
    
    # Test audio WebSocket
    audio_ok = await test_audio_websocket()
    print()
    
    # Summary
    print("📊 Test Summary:")
    print(f"   Simple WebSocket: {'✅ PASS' if simple_ok else '❌ FAIL'}")
    print(f"   Audio WebSocket:  {'✅ PASS' if audio_ok else '❌ FAIL'}")
    
    if simple_ok and audio_ok:
        print("\n🎉 All WebSocket tests PASSED!")
        print("🌐 You can now test in browser at: http://localhost:5001/stream-test")
    elif simple_ok:
        print("\n⚠️ Simple WebSocket works, but audio WebSocket has issues.")
        print("💡 Check server logs for service initialization errors.")
    else:
        print("\n❌ WebSocket connections are not working.")
        print("💡 Make sure the server is running: python app.py")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    except Exception as e:
        print(f"\n💥 Test error: {e}")