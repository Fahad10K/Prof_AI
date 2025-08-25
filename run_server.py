#!/usr/bin/env python3
"""
ProfAI Production Server Runner
Main entry point for the ProfAI application
"""

import uvicorn
from config import HOST, PORT, DEBUG

if __name__ == "__main__":
    print("🚀 Starting ProfAI Production Server...")
    print(f"📍 Server will be available at: http://{HOST}:{PORT}")
    print(f"🔧 Debug mode: {'ON' if DEBUG else 'OFF'}")
    print("=" * 50)
    
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if DEBUG else "warning"
    )