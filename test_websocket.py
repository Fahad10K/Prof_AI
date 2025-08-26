#!/usr/bin/env python3
"""
Simple WebSocket test script to verify the audio streaming endpoint
"""

import asyncio
import websockets
import json
import sys

async def test_websocket():
    """Test the WebSocket audio streaming endpoint."""
    uri = "ws://localhost:5001/ws/audio-stream"
    
    try:
        print(f"🔗 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            
            # Wait for connection ready message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Received: {data}")
            
            # Send a ping test
            print("📤 Sending ping...")
            await websocket.send(json.dumps({
                "type": "ping"
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Ping response: {data}")
            
            # Test audio generation
            print("📤 Testing audio generation...")
            await websocket.send(json.dumps({
                "type": "audio_only",
                "text": "Hello, this is a test message for audio generation.",
                "language": "en-IN"
            }))
            
            # Receive responses
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    print(f"📨 {data['type']}: {data.get('message', data.get('error', 'No message'))}")
                    
                    if data['type'] == 'audio_stream_complete':
                        print("✅ Audio generation completed successfully!")
                        break
                    elif data['type'] == 'error':
                        print(f"❌ Error: {data['error']}")
                        break
                        
                except asyncio.TimeoutError:
                    print("⏰ Timeout waiting for response")
                    break
                    
    except ConnectionRefusedError:
        print("❌ Connection refused. Make sure the server is running on localhost:5001")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

async def main():
    """Main test function."""
    print("🧪 WebSocket Audio Streaming Test")
    print("=" * 40)
    
    success = await test_websocket()
    
    if success:
        print("\n✅ WebSocket test completed successfully!")
        print("🌐 You can now test in browser at: http://localhost:5001/stream-test")
    else:
        print("\n❌ WebSocket test failed!")
        print("💡 Make sure to:")
        print("   1. Start the server: python app.py")
        print("   2. Check that services are initialized properly")
        print("   3. Verify your API keys are configured")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)