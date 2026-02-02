
import sys
import os
import asyncio
import logging
from unittest.mock import MagicMock

# Add project root
sys.path.append(os.getcwd())

from src.cogs.handlers.router_monitor import router_monitor, RouterHealthMonitor

async def verify_s7_anomalies():
    print("--- S7 Verification: Router Anomaly Detection ---")
    
    # 1. Reset Monitor for Testing
    router_monitor.events.clear()
    
    print("1. Injecting Healthy Traffic (90 requests)...")
    for i in range(90):
        router_monitor.add_event({
            "request_id": f"req_{i}",
            "retry_count": 0,
            "fallback_triggered": False,
            "router_roundtrip_ms": 100,
            "prefix_hash": "hash_A",
            "tools_bundle_id": "bundle_X"
        })
        
    metrics = router_monitor.get_metrics()
    print(f"   Status: {metrics['status']}")
    print(f"   Fallback Rate: {metrics['metrics']['fallback_rate_percent']}%")
    assert metrics['status'] == "HEALTHY"
    assert metrics['metrics']['fallback_rate_percent'] == 0.0
    
    print("\n2. Injecting Anomalies (High Latency + Fallback + Bundle Instability)...")
    # Add 15 failing requests to push fallback rate > 10%
    for i in range(15):
        router_monitor.add_event({
            "request_id": f"fail_{i}",
            "input_snippet": f"Test input {i}",
            "selected_categories": ["FAILED"],
            "retry_count": 2,
            "fallback_triggered": True,
            "router_roundtrip_ms": 100,
            "prefix_hash": "hash_B", # Matches bundle_X? No wait, let's mix it up
            "tools_bundle_id": "bundle_X" # Same bundle, different hash from hash_A above?
        })
        
    # Note: earlier we added hash_A for bundle_X. Now adding hash_B for bundle_X.
    # This should trigger Bundle Stability Violation.

    # Mock Logger to capture Context Dump
    from src.cogs.handlers.router_monitor import logger
    mock_logger = MagicMock()
    # We can't easily swap the module-level logger instance without patching logging.getLogger
    # Instead, we will rely on observing the alerts in the metrics, and manually checking logic path.
    # Or strict mocking:
    router_monitor._dump_critical_context = MagicMock(wraps=router_monitor._dump_critical_context)

    metrics = router_monitor.get_metrics()
    print(f"   Status: {metrics['status']}")
    print(f"   Fallback Rate: {metrics['metrics']['fallback_rate_percent']}%")
    print(f"   Unstable Bundles: {metrics['metrics']['unstable_bundles_count']}")
    
    print("   Alerts:")
    for alert in metrics['alerts']:
        print(f"   - {alert}")
        
    # Assertions
    assert metrics['status'] == "CRITICAL"
    assert "CRITICAL: High Fallback Rate" in str(metrics['alerts'])
    assert "WARNING: Bundle Stability Violation" in str(metrics['alerts'])
    assert metrics['metrics']['unstable_bundles_count'] == 1 # bundle_X is unstable
    
    # Verify S8-A Context Dump was called
    router_monitor._dump_critical_context.assert_called_once()
    print("✅ S8-A: Context Dump triggered successfully.")
    
    # Check singleton behavior
    new_instance = RouterHealthMonitor()
    assert new_instance is router_monitor
    assert len(new_instance.events) == 100 # Max window size
    
    print("\n✅ Verification Complete: Anomaly Detection Logic is Sound.")

if __name__ == "__main__":
    asyncio.run(verify_s7_anomalies())
