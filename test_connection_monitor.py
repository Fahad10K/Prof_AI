#!/usr/bin/env python3
"""
Test script for connection monitoring utilities.

This script tests the connection monitoring utilities to ensure they work correctly
for detecting normal vs abnormal disconnections and connection state checking.
"""

import sys
import asyncio
from unittest.mock import Mock
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError

# Add the current directory to the path so we can import our modules
sys.path.insert(0, '.')

from utils.connection_monitor import (
    is_normal_closure,
    is_abnormal_disconnection,
    get_disconnection_emoji,
    is_client_connected,
    is_client_disconnected,
    should_continue_streaming,
    send_chunk_safely,
    log_disconnection,
    get_connection_status,
    validate_connection_before_operation,
    ConnectionStateMonitor,
    create_connection_monitor
)

def test_normal_closure_detection():
    """Test normal closure detection."""
    print("Testing normal closure detection...")
    
    # Test ConnectionClosedOK (create with proper parameters)
    try:
        normal_exception = ConnectionClosedOK(None, None)
        assert is_normal_closure(normal_exception) == True
        assert is_abnormal_disconnection(normal_exception) == False
        assert get_disconnection_emoji(normal_exception) == "🔌"
    except Exception:
        # If ConnectionClosedOK constructor fails, create a mock
        normal_exception = Mock()
        normal_exception.__class__ = ConnectionClosedOK
        assert is_normal_closure(normal_exception) == True
        assert get_disconnection_emoji(normal_exception) == "🔌"
    
    # Test ConnectionClosed with normal codes (create with proper parameters)
    try:
        normal_1000 = ConnectionClosed(None, None)
        normal_1000.code = 1000
        assert is_normal_closure(normal_1000) == True
        assert get_disconnection_emoji(normal_1000) == "🔌"
        
        normal_1001 = ConnectionClosed(None, None)
        normal_1001.code = 1001
        assert is_normal_closure(normal_1001) == True
        assert get_disconnection_emoji(normal_1001) == "🔌"
        
        # Test abnormal closure
        abnormal_exception = ConnectionClosed(None, None)
        abnormal_exception.code = 1006
        assert is_normal_closure(abnormal_exception) == False
        assert is_abnormal_disconnection(abnormal_exception) == True
        assert get_disconnection_emoji(abnormal_exception) == "❌"
        
    except Exception:
        # If ConnectionClosed constructor fails, create mocks
        normal_1000 = Mock()
        normal_1000.__class__ = ConnectionClosed
        normal_1000.code = 1000
        assert is_normal_closure(normal_1000) == True
        assert get_disconnection_emoji(normal_1000) == "🔌"
        
        abnormal_exception = Mock()
        abnormal_exception.__class__ = ConnectionClosed
        abnormal_exception.code = 1006
        assert is_normal_closure(abnormal_exception) == False
        assert get_disconnection_emoji(abnormal_exception) == "❌"
    
    print("✅ Normal closure detection tests passed")

def test_connection_state_checking():
    """Test connection state checking utilities."""
    print("Testing connection state checking...")
    
    # Test with None websocket
    assert is_client_connected(None) == False
    assert is_client_disconnected(None) == True
    assert should_continue_streaming(None) == False
    
    # Test with mock connected websocket
    connected_ws = Mock()
    connected_ws.closed = False
    connected_ws.state = 1  # OPEN
    connected_ws.open = True
    
    assert is_client_connected(connected_ws) == True
    assert is_client_disconnected(connected_ws) == False
    assert should_continue_streaming(connected_ws) == True
    
    # Test with mock disconnected websocket
    disconnected_ws = Mock()
    disconnected_ws.closed = True
    disconnected_ws.state = 3  # CLOSED
    disconnected_ws.open = False
    
    assert is_client_connected(disconnected_ws) == False
    assert is_client_disconnected(disconnected_ws) == True
    assert should_continue_streaming(disconnected_ws) == False
    
    print("✅ Connection state checking tests passed")

async def test_safe_chunk_sending():
    """Test safe chunk sending."""
    print("Testing safe chunk sending...")
    
    # Test with disconnected websocket
    disconnected_ws = Mock()
    disconnected_ws.closed = True
    disconnected_ws.state = 3  # CLOSED
    
    result = await send_chunk_safely(disconnected_ws, {"type": "test"}, "test_client")
    assert result == False
    
    # Test with connected websocket
    connected_ws = Mock()
    connected_ws.closed = False
    connected_ws.state = 1  # OPEN
    connected_ws.send = Mock(return_value=asyncio.Future())
    connected_ws.send.return_value.set_result(None)
    
    result = await send_chunk_safely(connected_ws, {"type": "test"}, "test_client")
    assert result == True
    
    print("✅ Safe chunk sending tests passed")

def test_connection_status():
    """Test connection status utilities."""
    print("Testing connection status utilities...")
    
    # Test with mock websocket
    ws = Mock()
    ws.closed = False
    ws.state = 1  # OPEN
    ws.open = True
    
    status = get_connection_status(ws, "test_client")
    assert status["client_id"] == "test_client"
    assert status["is_connected"] == True
    assert status["state"] == "OPEN"
    assert status["closed"] == False
    assert status["open"] == True
    
    # Test validation
    assert validate_connection_before_operation(ws, "test_client", "test_operation") == True
    
    ws.closed = True
    ws.state = 3  # CLOSED
    assert validate_connection_before_operation(ws, "test_client", "test_operation") == False
    
    print("✅ Connection status tests passed")

def test_connection_monitor():
    """Test ConnectionStateMonitor class."""
    print("Testing ConnectionStateMonitor...")
    
    monitor = create_connection_monitor("test_client")
    assert isinstance(monitor, ConnectionStateMonitor)
    assert monitor.client_id == "test_client"
    
    # Test recording activity
    monitor.record_chunk_sent(1024)
    assert monitor.chunks_sent == 1
    assert monitor.bytes_sent == 1024
    
    # Test recording disconnections with mock exceptions
    normal_exception = Mock()
    normal_exception.__class__ = ConnectionClosedOK
    monitor.record_disconnection(normal_exception)
    assert monitor.normal_disconnections == 1
    assert monitor.error_disconnections == 0
    
    abnormal_exception = Mock()
    abnormal_exception.__class__ = ConnectionClosed
    abnormal_exception.code = 1006
    monitor.record_disconnection(abnormal_exception)
    assert monitor.normal_disconnections == 1
    assert monitor.error_disconnections == 1
    
    # Test metrics
    metrics = monitor.get_metrics()
    assert metrics["client_id"] == "test_client"
    assert metrics["chunks_sent"] == 1
    assert metrics["bytes_sent"] == 1024
    assert metrics["normal_disconnections"] == 1
    assert metrics["error_disconnections"] == 1
    assert metrics["total_disconnections"] == 2
    
    # Test health check
    assert monitor.is_healthy_connection() == True
    
    print("✅ ConnectionStateMonitor tests passed")

async def main():
    """Run all tests."""
    print("🧪 Testing Connection Monitoring Utilities")
    print("=" * 50)
    
    try:
        test_normal_closure_detection()
        test_connection_state_checking()
        await test_safe_chunk_sending()
        test_connection_status()
        test_connection_monitor()
        
        print("=" * 50)
        print("🎉 All tests passed! Connection monitoring utilities are working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())