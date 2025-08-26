#!/usr/bin/env python3
"""
Debug and Fix Script for ProfAI Issues
"""

import sys
import os
import requests
import json
import time

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_server_connection():
    """Test if server is running and responding."""
    try:
        response = requests.get("http://127.0.0.1:5001/health", timeout=5)
        print(f"✅ Server is running - Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   Services Available: {health_data.get('services_available', 'Unknown')}")
            services = health_data.get('services', {})
            for service, status in services.items():
                status_icon = "✅" if status else "❌"
                print(f"   {status_icon} {service}: {status}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running on http://127.0.0.1:5001")
        return False
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        return False

def test_chat_endpoint():
    """Test the chat endpoint specifically."""
    try:
        print("\\n🔍 Testing Chat Endpoint...")
        response = requests.post(
            "http://127.0.0.1:5001/api/chat",
            json={"message": "Hello, test message", "language": "en-IN"},
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("   ✅ Chat endpoint working!")
            data = response.json()
            print(f"   Response keys: {list(data.keys())}")
        else:
            print(f"   ❌ Chat endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Chat test error: {e}")

def test_courses_endpoint():
    """Test courses endpoint."""
    try:
        print("\\n📚 Testing Courses Endpoint...")
        response = requests.get("http://127.0.0.1:5001/api/courses", timeout=10)
        
        if response.status_code == 200:
            courses = response.json()
            print(f"   ✅ Found {len(courses)} courses")
            if courses:
                course = courses[0]
                print(f"   First course: {course.get('course_title', 'Unknown')}")
                return course.get('course_id')
        else:
            print(f"   ❌ Courses endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Courses test error: {e}")
    
    return None

def test_class_endpoints(course_id):
    """Test class-related endpoints."""
    if not course_id:
        print("\\n⚠️ No course ID available for class testing")
        return
        
    try:
        print("\\n🎓 Testing Class Endpoints...")
        
        # Test class content stream
        response = requests.post(
            "http://127.0.0.1:5001/api/class-content-stream",
            json={
                "course_id": course_id,
                "module_index": 0,
                "sub_topic_index": 0,
                "language": "en-IN"
            },
            timeout=30
        )
        
        print(f"   Class Content Stream - Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   ❌ Error: {response.text}")
        else:
            print("   ✅ Class content stream working")
            
    except Exception as e:
        print(f"   ❌ Class endpoints test error: {e}")

def check_environment():
    """Check environment variables and configuration."""
    print("\\n🔧 Checking Environment...")
    
    try:
        import config
        print("   ✅ Config module loaded")
        
        # Check important config values
        if hasattr(config, 'OPENAI_API_KEY'):
            key_preview = config.OPENAI_API_KEY[:10] + "..." if config.OPENAI_API_KEY else "Not set"
            print(f"   OpenAI API Key: {key_preview}")
        
        if hasattr(config, 'SARVAM_API_KEY'):
            key_preview = config.SARVAM_API_KEY[:10] + "..." if config.SARVAM_API_KEY else "Not set"
            print(f"   Sarvam API Key: {key_preview}")
            
    except Exception as e:
        print(f"   ❌ Config check error: {e}")

def check_services():
    """Check if services can be imported and initialized."""
    print("\\n🔧 Checking Services...")
    
    try:
        from services.chat_service import ChatService
        print("   ✅ ChatService import successful")
        
        from services.audio_service import AudioService
        print("   ✅ AudioService import successful")
        
        from services.teaching_service import TeachingService
        print("   ✅ TeachingService import successful")
        
        from services.document_service import DocumentService
        print("   ✅ DocumentService import successful")
        
    except Exception as e:
        print(f"   ❌ Service import error: {e}")

def main():
    """Run comprehensive diagnostics."""
    print("🚀 ProfAI Comprehensive Diagnostic Tool")
    print("=" * 60)
    
    # Check environment
    check_environment()
    
    # Check service imports
    check_services()
    
    # Test server connection
    if not test_server_connection():
        print("\\n❌ Cannot proceed with endpoint tests - server not running")
        print("\\n💡 To start the server, run: python run_server.py")
        return
    
    # Test individual endpoints
    test_chat_endpoint()
    
    course_id = test_courses_endpoint()
    test_class_endpoints(course_id)
    
    print("\\n" + "=" * 60)
    print("🏁 Diagnostic Complete!")
    print("\\n💡 If issues persist:")
    print("   1. Check server logs for detailed error messages")
    print("   2. Verify API keys in .env file")
    print("   3. Ensure all dependencies are installed")
    print("   4. Try restarting the server")

if __name__ == "__main__":
    main()