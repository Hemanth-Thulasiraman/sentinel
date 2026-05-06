# tests/tools/mock_metrics_api.py

def get_mock_metrics(service_name: str, timestamp: str) -> dict:
    return {
        "cpu_spike": True if "auth" in service_name else False,
        "error_rate": 14.3,
        "latency_p99": 2840,
        "anomaly_detected": True,
        "data_available": True,
    }