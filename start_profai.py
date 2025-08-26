#!/usr/bin/env python3
"""
ProfAI Startup Script
Starts both the FastAPI web server and WebSocket server for real-time audio streaming
"""

import os
import sys
import time
import subprocess
import threading

def print_banner():
    """Print startup banner."""
    print("=" * 60)
    print("🎓 ProfAI - AI-Powered Educational Assistant")
    print("=" * 60)
    print("🚀 Starting servers...")
    print()

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import fastapi
        import websockets
        import sarvamai
        import openai
        print("✅ All dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install required packages:")
        print("pip install fastapi uvicorn websockets sarvamai openai langchain chromadb")
        return False

def start_servers():
    """Start the ProfAI servers."""
    if not check_dependencies():
        return
    
    print_banner()
    
    try:
        # Start the main application (includes both FastAPI and WebSocket)
        print("🌐 Starting ProfAI servers...")
        print("   - FastAPI server: http://localhost:5001")
        print("   - WebSocket server: ws://localhost:8765")
        print("   - Web interface: http://localhost:5001/")
        print()
        print("📝 Logs:")
        print("-" * 30)
        
        # Run the main app
        subprocess.run([sys.executable, "app.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down ProfAI servers...")
    except Exception as e:
        print(f"❌ Error starting servers: {e}")

if __name__ == "__main__":
    start_servers()