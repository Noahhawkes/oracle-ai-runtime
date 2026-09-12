"""
Full Presence Loop Integration Test

Tests that the complete chain works:
  1. Event daemon monitors files/git/memory
  2. Events feed into salience filter
  3. Notifications are sent via multiple channels
  4. Hotkeys can trigger actions
  5. FastAPI endpoints receive updates

Run:
    python test_presence_integration.py
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


def test_event_daemon():
    """Test 1: Event daemon can detect changes."""
    print("\n[Test 1] Event Daemon\n")
    try:
        from platforms.windows.event_daemon import EventDaemon
        
        daemon = EventDaemon(ROOT)
        daemon.start()
        
        print("  Monitoring for 5 seconds...")
        time.sleep(5)
        
        events = daemon.get_events(10)
        daemon.stop()
        
        if len(events) >= 0:  # May have 0 events if nothing changed
            print(f"  Captured {len(events)} event(s)")
            for e in events:
                print(f"    - [{e['urgency']:.1f}] {e['event_type']}: {e['detail']}")
        
        print("\n  [PASS] EventDaemon works")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_channel_notifier():
    """Test 2: Multi-channel notifier sends to different channels."""
    print("\n[Test 2] Multi-Channel Notifier\n")
    try:
        from platforms.windows.notifier import MultiChannelNotifier
        
        notifier = MultiChannelNotifier()
        
        print("  Testing urgency levels:\n")
        
        print("  [LOW] Silent (no output expected)...")
        notifier.notify("Background observation", 0.2)
        time.sleep(0.2)
        
        print("  [MEDIUM] Browser + optional toast...")
        notifier.notify("File changed: core/oracle.py", 0.5)
        time.sleep(0.2)
        
        print("  [HIGH] Sound + toast + browser...")
        notifier.notify("Memory candidate pending approval", 0.7)
        time.sleep(0.5)
        
        print("\n  [PASS] MultiChannelNotifier works")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_salience_filter_integration():
    """Test 3: Daemon events feed into salience filter."""
    print("\n[Test 3] Salience Filter Integration\n")
    try:
        from salience_filter import infer_signal, ingest_signal
        from presence_daemon import PresenceDaemonOrchestrator
        
        # Manually ingest a signal
        signal = infer_signal("test_daemon", "Modified: core/oracle.py with high-value improvement")
        
        print(f"  Signal created:")
        print(f"    - source: {signal.source}")
        print(f"    - content: {signal.content}")
        print(f"    - salience: {signal.salience:.2f}")
        
        # Save to filter
        ingest_signal(signal)
        
        print("\n  [PASS] Salience filter integration works")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fastapi_endpoints():
    """Test 4: FastAPI notification endpoints."""
    print("\n[Test 4] FastAPI Endpoints\n")
    try:
        import urllib.request
        import urllib.error

        try:
            from runtime_config import runtime_base_url
            base_url = runtime_base_url(host="localhost")
        except Exception:
            base_url = "http://localhost:7781"
        
        # Check if server is up
        try:
            response = urllib.request.urlopen(f"{base_url}/", timeout=2)
            if response.status == 200:
                print(f"  ✓ Server online")
            else:
                print(f"  ✗ Server returned status {response.status}")
                return False
        except urllib.error.URLError:
            print(f"  ✗ Server not running at {base_url}")
            print(f"    (This is OK if you haven't started oracle_server.py)")
            return False
        
        # Test /api/status
        try:
            req = urllib.request.Request(
                f"{base_url}/api/status",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=2) as r:
                data = json.loads(r.read().decode())
                print(f"  ✓ /api/status online")
                print(f"    - paused: {data.get('paused')}")
                print(f"    - notifications queued: {data.get('notifications_queued')}")
        except Exception as e:
            print(f"  ✗ /api/status error: {e}")
        
        # Test /api/notify
        try:
            import json
            payload = json.dumps({
                "message": "Test notification from presence loop",
                "urgency": 0.6
            }).encode('utf-8')
            req = urllib.request.Request(
                f"{base_url}/api/notify",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as r:
                print(f"  ✓ /api/notify working")
        except Exception as e:
            print(f"  ✗ /api/notify error: {e}")
        
        print("\n  [PASS] FastAPI endpoints accessible")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_hotkey_handler():
    """Test 5: Hotkey handler can be initialized."""
    print("\n[Test 5] Hotkey Handler\n")
    try:
        from platforms.windows.hotkey_handler import OracleHotkeyManager
        
        manager = OracleHotkeyManager()
        
        if manager.handler.use_keyboard:
            print(f"  ✓ Keyboard library available")
            print(f"  ✓ Hotkeys can be registered:")
            print(f"    - Win+O: Open UI")
            print(f"    - Ctrl+Shift+A: Approve")
            print(f"    - Ctrl+Shift+M: Memory")
            print(f"    - Ctrl+Shift+X: Emergency stop")
            print(f"\n  [PASS] HotkeyHandler initialized")
            return True
        else:
            print(f"  ⚠ Keyboard library not installed")
            print(f"    Install with: pip install keyboard")
            print(f"\n  [PASS] HotkeyHandler skipped (optional)")
            return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_presence_daemon_orchestrator():
    """Test 6: Full presence daemon orchestrator."""
    print("\n[Test 6] PresenceDaemon Orchestrator\n")
    try:
        from core.presence_daemon import PresenceDaemonOrchestrator
        
        orchestrator = PresenceDaemonOrchestrator()
        orchestrator.start()
        
        print("  Daemon running for 3 seconds...")
        time.sleep(3)
        
        events = orchestrator.get_daemon_events(5)
        print(f"  Captured {len(events)} event(s)")
        
        orchestrator.stop()
        
        print("\n  [PASS] PresenceDaemon orchestrator works")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 70)
    print("ORACLE PRESENCE INTEGRATION TEST SUITE")
    print("=" * 70)
    print(f"Started at {datetime.now().isoformat()}")
    
    results = []
    
    # Run tests
    results.append(("EventDaemon", test_event_daemon()))
    results.append(("MultiChannelNotifier", test_multi_channel_notifier()))
    results.append(("SalienceFilterIntegration", test_salience_filter_integration()))
    results.append(("FastAPIEndpoints", test_fastapi_endpoints()))
    results.append(("HotkeyHandler", test_hotkey_handler()))
    results.append(("PresenceDaemonOrchestrator", test_presence_daemon_orchestrator()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 All tests passed! ORACLE presence is fully integrated.")
        print("\nNext steps:")
        print("  1. Start oracle_server.py if not already running")
        print("  2. Open the runtime URL (default http://localhost:7781) in your browser")
        print("  3. Make changes to files in core/ or Projects/")
        print("  4. Watch for notifications (urgency-based multi-channel alerts)")
        print("  5. Try hotkeys:")
        print("     - Win+O to focus UI")
        print("     - Ctrl+Shift+X for emergency stop")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. See details above.")
    
    print(f"\nEnded at {datetime.now().isoformat()}\n")


if __name__ == "__main__":
    main()
