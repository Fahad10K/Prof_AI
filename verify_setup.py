#!/usr/bin/env python3
"""
ProfAI Setup Verification Script
Checks if all services are running and accessible
"""

import asyncio
import aiohttp
import websockets
import json
import sys
import os

API_BASE_URL = "http://localhost:5001"
WS_URL = "ws://localhost:8765"

async def test_api_health():
    """Test API health endpoint."""
    print("🔍 Testing API health...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ API Health: {data}")
                    return True
                else:
                    print(f"❌ API Health failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False

async def test_websocket():
    """Test WebSocket connection."""
    print("🔍 Testing WebSocket connection...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Send ping
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("type") == "connection_ready":
                print("✅ WebSocket connected and ready")
                return True
            else:
                print(f"✅ WebSocket response: {data}")
                return True
                
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

async def test_courses_api():
    """Test courses API."""
    print("🔍 Testing courses API...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/api/courses") as response:
                if response.status == 200:
                    courses = await response.json()
                    print(f"✅ Courses API: Found {len(courses)} courses")
                    if len(courses) == 0:
                        print("⚠️  No courses available - upload PDFs to generate content")
                    return True
                else:
                    print(f"❌ Courses API failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Courses API failed: {e}")
        return False

async def test_chat_websocket():
    """Test chat via WebSocket."""
    print("🔍 Testing chat via WebSocket...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Wait for connection ready
            ready_msg = await websocket.recv()
            print(f"📨 Connection: {json.loads(ready_msg)}")
            
            # Send chat message
            chat_msg = {
                "type": "chat_with_audio",
                "message": "Hello, this is a test",
                "language": "en-IN"
            }
            await websocket.send(json.dumps(chat_msg))
            print("📤 Sent test chat message")
            
            # Wait for responses
            responses = 0
            while responses < 3:  # Wait for a few responses
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    print(f"📨 Response {responses + 1}: {data.get('type', 'unknown')}")
                    responses += 1
                    
                    if data.get("type") == "error":
                        print(f"❌ Chat error: {data.get('error')}")
                        return False
                        
                except asyncio.TimeoutError:
                    break
            
            print("✅ Chat WebSocket test completed")
            return True
            
    except Exception as e:
        print(f"❌ Chat WebSocket test failed: {e}")
        return False

def check_files():
    """Check if required files exist."""
    print("🔍 Checking required files...")
    
    required_files = [
        "app.py",
        "websocket_server.py",
        "web/index.html",
        "services/chat_service.py",
        "services/audio_service.py",
        "config.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

async def main():
    """Run all verification tests."""
    print("🚀 ProfAI Setup Verification")
    print("=" * 50)
    
    # Check files
    files_ok = check_files()
    
    # Test API
    api_ok = await test_api_health()
    
    # Test WebSocket
    ws_ok = await test_websocket()
    
    # Test courses
    courses_ok = await test_courses_api()
    
    # Test chat (optional)
    chat_ok = True
    if api_ok and ws_ok:
        chat_ok = await test_chat_websocket()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Verification Summary:")
    print(f"   Files: {'✅' if files_ok else '❌'}")
    print(f"   API: {'✅' if api_ok else '❌'}")
    print(f"   WebSocket: {'✅' if ws_ok else '❌'}")
    print(f"   Courses: {'✅' if courses_ok else '❌'}")
    print(f"   Chat: {'✅' if chat_ok else '❌'}")
    
    if all([files_ok, api_ok, ws_ok, courses_ok]):
        print("\n🎉 All systems operational!")
        print("🌐 Open http://localhost:5001/ to use ProfAI")
        return True
    else:
        print("\n⚠️  Some issues detected. Check the logs above.")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n🛑 Verification cancelled")
        sys.exit(1)