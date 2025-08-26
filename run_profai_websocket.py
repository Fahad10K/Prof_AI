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

def start_fastapi_server():
    """Start FastAPI server in a separate thread."""
    import uvicorn
    from app import app
    
    print("🚀 Starting FastAPI server on http://localhost:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")

def start_websocket_server():
    """Start WebSocket server."""
    from websocket_server import start_websocket_server
    
    print("🌐 Starting WebSocket server on ws://localhost:8765")
    asyncio.run(start_websocket_server("0.0.0.0", 8765))

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
        
        # Start WebSocket server (blocking)
        start_websocket_server()
        
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