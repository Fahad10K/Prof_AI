#!/usr/bin/env python3
"""
Comprehensive WebSocket diagnostic script
"""

import asyncio
import sys
import os
import traceback

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_environment():
    """Check environment variables and dependencies."""
    print("🔍 Environment Check")
    print("-" * 30)
    
    # Check API keys
    api_keys = ["OPENAI_API_KEY", "SARVAM_API_KEY", "GROQ_API_KEY"]
    for key in api_keys:
        value = os.getenv(key)
        if value:
            print(f"   ✅ {key}: {'*' * 8}{value[-4:]}")
        else:
            print(f"   ❌ {key}: Not set")
    
    # Check Python packages
    packages = [
        "websockets", "asyncio", "json", "time", "logging",
        "sarvamai", "openai", "langchain", "chromadb"
    ]
    
    print("\n📦 Package Check")
    print("-" * 30)
    
    for package in packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError as e:
            print(f"   ❌ {package}: {e}")

def test_service_imports():
    """Test importing all services."""
    print("\n🔧 Service Import Test")
    print("-" * 30)
    
    services = [
        ("config", "config"),
        ("ChatService", "services.chat_service"),
        ("AudioService", "services.audio_service"),
        ("TeachingService", "services.teaching_service"),
        ("SarvamService", "services.sarvam_service"),
        ("LLMService", "services.llm_service"),
        ("DocumentService", "services.document_service")
    ]
    
    for service_name, module_path in services:
        try:
            if service_name == "config":
                import config
                print(f"   ✅ {service_name}")
            else:
                module = __import__(module_path, fromlist=[service_name])
                service_class = getattr(module, service_name)
                print(f"   ✅ {service_name}")
        except Exception as e:
            print(f"   ❌ {service_name}: {e}")

async def test_service_initialization():
    """Test initializing all services."""
    print("\n🚀 Service Initialization Test")
    print("-" * 30)
    
    # Test individual services
    services_to_test = [
        ("SarvamService", "services.sarvam_service"),
        ("LLMService", "services.llm_service"),
        ("AudioService", "services.audio_service"),
        ("TeachingService", "services.teaching_service"),
        ("ChatService", "services.chat_service")
    ]
    
    initialized_services = {}
    
    for service_name, module_path in services_to_test:
        try:
            print(f"   🔄 Initializing {service_name}...")
            module = __import__(module_path, fromlist=[service_name])
            service_class = getattr(module, service_name)
            service_instance = service_class()
            initialized_services[service_name] = service_instance
            print(f"   ✅ {service_name} initialized successfully")
        except Exception as e:
            print(f"   ❌ {service_name} failed: {e}")
            traceback.print_exc()
    
    return initialized_services

async def test_websocket_server():
    """Test WebSocket server startup."""
    print("\n🌐 WebSocket Server Test")
    print("-" * 30)
    
    try:
        print("   🔄 Importing WebSocket server...")
        from websocket_server import start_websocket_server
        print("   ✅ WebSocket server imported")
        
        print("   🔄 Starting server on port 8768 (test)...")
        
        # Start server with very short timeout
        server_task = asyncio.create_task(start_websocket_server("localhost", 8768))
        
        # Let it run for 2 seconds
        await asyncio.sleep(2)
        
        # Cancel the server
        server_task.cancel()
        
        try:
            await server_task
        except asyncio.CancelledError:
            print("   ✅ Server started and stopped successfully")
            return True
        
    except Exception as e:
        print(f"   ❌ WebSocket server test failed: {e}")
        traceback.print_exc()
        return False

async def test_audio_streaming():
    """Test audio streaming functionality."""
    print("\n🎵 Audio Streaming Test")
    print("-" * 30)
    
    try:
        from services.audio_service import AudioService
        audio_service = AudioService()
        
        print("   🔄 Testing audio streaming...")
        
        test_text = "Hello, this is a test of the audio streaming system."
        chunk_count = 0
        
        async for chunk in audio_service.stream_audio_from_text(test_text, "en-IN"):
            chunk_count += 1
            if chunk and len(chunk) > 0:
                print(f"   📦 Received chunk {chunk_count}: {len(chunk)} bytes")
                if chunk_count >= 3:  # Limit test to first 3 chunks
                    break
        
        if chunk_count > 0:
            print(f"   ✅ Audio streaming working: {chunk_count} chunks received")
            return True
        else:
            print("   ❌ No audio chunks received")
            return False
            
    except Exception as e:
        print(f"   ❌ Audio streaming test failed: {e}")
        traceback.print_exc()
        return False

async def main():
    """Run all diagnostic tests."""
    print("🩺 ProfAI WebSocket Diagnostic Tool")
    print("=" * 50)
    
    # Environment check
    check_environment()
    
    # Service import test
    test_service_imports()
    
    # Service initialization test
    services = await test_service_initialization()
    
    # WebSocket server test
    server_ok = await test_websocket_server()
    
    # Audio streaming test
    audio_ok = await test_audio_streaming()
    
    # Summary
    print("\n📊 Diagnostic Summary")
    print("=" * 50)
    
    if server_ok:
        print("✅ WebSocket server: OK")
    else:
        print("❌ WebSocket server: FAILED")
    
    if audio_ok:
        print("✅ Audio streaming: OK")
    else:
        print("❌ Audio streaming: FAILED")
    
    print(f"✅ Services initialized: {len(services)}")
    
    if server_ok and audio_ok:
        print("\n🎉 All systems appear to be working!")
        print("   Try running: python websocket_server.py")
    else:
        print("\n⚠️  Some issues detected. Check the logs above.")

if __name__ == "__main__":
    asyncio.run(main())