#!/usr/bin/env python3
"""
ProfAI WebSocket Server Startup Script
Starts both the FastAPI server and WebSocket server for optimal performance
"""

import asyncio
import threading
import time
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

  
if hasattr(sys, '_clear_type_cache'):
    sys._clear_type_cache()

# Clear any existing module cache for our services
modules_to_clear = [mod for mod in sys.modules if 'sarvam' in mod.lower()]
for mod in modules_to_clear:
    del sys.modules[mod]

def start_fastapi_server():
    """Start FastAPI server in a separate thread with proper async handling."""
    try:
        import uvicorn
        from app import app
        
        print("🚀 Starting FastAPI server on http://localhost:5001")
        # Create completely isolated event loop for FastAPI thread
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run without loop parameter to avoid ProactorEventLoop error
        uvicorn.run(app, host="0.0.0.0", port=5001, log_level="warning")
    except Exception as e:
        print(f"❌ FastAPI startup error: {e}")
        import traceback
        traceback.print_exc()

async def start_websocket_server_async():
    """Start WebSocket server asynchronously."""
    from websocket_server import start_websocket_server
    
    print("🌐 Starting WebSocket server on ws://localhost:8765")
    await start_websocket_server("0.0.0.0", 8765)

def main():
    """Main startup function."""
    print("=" * 60)
    print("🎓 ProfAI - High Performance WebSocket Server")
    print("=" * 60)
    print("Features:")
    print("  • Sub-300ms audio latency")
    print("  • Real-time streaming")
    print("  • Educational content delivery")
    print("  • Multi-language support")
    print("=" * 60)
    
    try:
        # Check if ports are available
        import socket
        
        def check_port(port, name):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result == 0:
                print(f"⚠️ Warning: Port {port} ({name}) appears to be in use")
                return False
            return True
        
        fastapi_available = check_port(5001, "FastAPI")
        websocket_available = check_port(8765, "WebSocket")
        
        if not fastapi_available or not websocket_available:
            print("💡 If you're running existing servers, you can:")
            print("   - Stop them and restart this script")
            print("   - Or just run: python websocket_server.py (WebSocket only)")
            print("   - Or just run: python app.py (FastAPI only)")
            
            response = input("\nContinue anyway? (y/N): ").lower().strip()
            if response != 'y':
                print("👋 Exiting...")
                return
        
        # Start FastAPI server in background thread
        print("\n🚀 Starting FastAPI server...")
        fastapi_thread = threading.Thread(target=start_fastapi_server, daemon=True)
        fastapi_thread.start()
        
        # Give FastAPI time to start
        time.sleep(3)
        
        print("✅ FastAPI server started")
        print("📱 Web interface: http://localhost:5001")
        print("🧪 WebSocket test: http://localhost:5001/profai-websocket-test")
        print("🔧 Quick test: python quick_test_websocket.py")
        print("\n🌐 Starting WebSocket server...")
        
        # Start WebSocket server (blocking) with proper async handling
        asyncio.run(start_websocket_server_async())
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down servers...")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Error starting servers: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check if ports 5001 and 8765 are available")
        print("   2. Verify all dependencies are installed")
        print("   3. Check the error message above for specific issues")
        sys.exit(1)

if __name__ == "__main__":
    main()