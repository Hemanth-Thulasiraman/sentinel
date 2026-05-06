# scripts/generate_sample_logs.py

import csv
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

def random_timestamp(start_days_ago: int = 30) -> datetime:
    now = datetime.now(timezone.utc)  # replace utcnow()
    start = now - timedelta(days=start_days_ago)
    random_seconds = random.randint(0, int((now - start).total_seconds()))
    return start + timedelta(seconds=random_seconds)

LOG_TEMPLATES = {
    "LOW": [
        {"service": "auth-service", "error_type": "successful_login", "template": "INFO auth-service {ip} - User {user} logged in successfully"},
        {"service": "nginx", "error_type": "static_asset_served", "template": "INFO nginx {ip} - GET /static/logo.png 200 12ms"},
        {"service": "api-gateway", "error_type": "health_check_passed", "template": "INFO api-gateway {ip} - Health check passed for upstream service"},
        {"service": "database", "error_type": "query_completed", "template": "INFO database {ip} - Read query completed in 18ms"},
        {"service": "user-service", "error_type": "profile_loaded", "template": "INFO user-service {ip} - User profile loaded for {user}"},
        {"service": "payment-service", "error_type": "payment_status_checked", "template": "INFO payment-service {ip} - Payment status lookup completed"},
        {"service": "nginx", "error_type": "request_completed", "template": "INFO nginx {ip} - GET /api/status 200 24ms"},
        {"service": "auth-service", "error_type": "token_refreshed", "template": "INFO auth-service {ip} - Token refreshed for user {user}"},
    ],
    "MEDIUM": [
        {"service": "auth-service", "error_type": "repeated_failed_login", "template": "WARNING auth-service {ip} - Failed login attempt for user {user}"},
        {"service": "api-gateway", "error_type": "upstream_latency", "template": "WARNING api-gateway {ip} - Upstream response latency exceeded 900ms"},
        {"service": "database", "error_type": "slow_query", "template": "WARNING database {ip} - Slow query detected on users table"},
        {"service": "nginx", "error_type": "rate_limit_warning", "template": "WARNING nginx {ip} - Client approaching rate limit threshold"},
        {"service": "user-service", "error_type": "cache_miss_spike", "template": "WARNING user-service {ip} - Cache miss rate increased for profile endpoint"},
        {"service": "payment-service", "error_type": "payment_retry", "template": "WARNING payment-service {ip} - Payment retry triggered for transaction"},
        {"service": "api-gateway", "error_type": "partial_upstream_failure", "template": "WARNING api-gateway {ip} - One upstream dependency returned intermittent failures"},
    ],
    "HIGH": [
        {"service": "auth-service", "error_type": "brute_force_detected", "template": "ERROR auth-service {ip} - Multiple failed logins detected from same IP"},
        {"service": "database", "error_type": "connection_pool_exhausted", "template": "ERROR database {ip} - Connection pool exhausted for primary database"},
        {"service": "payment-service", "error_type": "payment_failure_spike", "template": "ERROR payment-service {ip} - Payment failures exceeded normal threshold"},
        {"service": "api-gateway", "error_type": "upstream_unavailable", "template": "ERROR api-gateway {ip} - Upstream service unavailable for checkout route"},
        {"service": "nginx", "error_type": "five_xx_spike", "template": "ERROR nginx {ip} - 5xx responses spiked on /api/login"},
        {"service": "user-service", "error_type": "profile_write_failure", "template": "ERROR user-service {ip} - Failed to persist profile update for user {user}"},
        {"service": "database", "error_type": "replication_lag", "template": "ERROR database {ip} - Replica lag exceeded 120 seconds"},
    ],
    "CRITICAL": [
        {"service": "payment-service", "error_type": "data_breach_attempt", "template": "CRITICAL payment-service {ip} - Unauthorized access to payment records"},
        {"service": "auth-service", "error_type": "privilege_escalation", "template": "CRITICAL auth-service {ip} - Privilege escalation attempt detected for user {user}"},
        {"service": "database", "error_type": "primary_database_down", "template": "CRITICAL database {ip} - Primary database is unreachable"},
        {"service": "api-gateway", "error_type": "global_outage", "template": "CRITICAL api-gateway {ip} - All upstream services unavailable"},
        {"service": "nginx", "error_type": "suspected_ddos", "template": "CRITICAL nginx {ip} - Suspected DDoS traffic pattern detected"},
        {"service": "user-service", "error_type": "pii_exposure", "template": "CRITICAL user-service {ip} - Possible PII exposure detected in response payload"},
        {"service": "payment-service", "error_type": "fraud_rule_bypass", "template": "CRITICAL payment-service {ip} - Fraud detection bypass attempt detected"},
    ],
}


SERVICES = [
    "auth-service",
    "payment-service",
    "nginx",
    "database",
    "api-gateway",
    "user-service",
]

USERS = ["alice", "bob", "charlie", "admin", "root", "service-account"]

IPS = [
    "192.168.1.105",
    "10.0.0.23",
    "172.16.0.8",
    "203.0.113.42",
    "198.51.100.17",
]

SERVICE_ENCODING = {
    "auth-service": 0,
    "payment-service": 1,
    "nginx": 2,
    "database": 3,
    "api-gateway": 4,
    "user-service": 5,
}


def random_timestamp(start_days_ago: int = 30) -> datetime:
    now = datetime.utcnow()
    start = now - timedelta(days=start_days_ago)
    random_seconds = random.randint(0, int((now - start).total_seconds()))
    return start + timedelta(seconds=random_seconds)


def generate_log_row(severity: str) -> dict[str, Any]:
    template_info = random.choice(LOG_TEMPLATES[severity])
    timestamp = random_timestamp()

    service_name = template_info["service"]
    source_ip = random.choice(IPS)
    user = random.choice(USERS)

    message = template_info["template"].format(
        ip=source_ip,
        user=user,
        service=service_name,
    )

    raw_log = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {message}"

    return {
        "log_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat(),
        "service_name": service_name,
        "service_encoded": SERVICE_ENCODING[service_name],
        "error_type": template_info["error_type"],
        "severity_label": severity,
        "raw_log": raw_log,
        "message": message,
        "source_ip": source_ip,
        "hour_of_day": timestamp.hour,
        "is_weekend": timestamp.weekday() >= 5,
        "message_length": len(message),
    }


def generate_dataset(
    output_path: str = "data/processed/logs_labeled.csv",
    n_total: int = 5000,
    distribution: dict[str, float] | None = None,
) -> None:
    if distribution is None:
        distribution = {
            "LOW": 0.40,
            "MEDIUM": 0.30,
            "HIGH": 0.20,
            "CRITICAL": 0.10,
        }

    rows: list[dict[str, Any]] = []

    for severity, ratio in distribution.items():
        for _ in range(int(n_total * ratio)):
            rows.append(generate_log_row(severity))

    while len(rows) < n_total:
        rows.append(generate_log_row(random.choice(list(distribution.keys()))))

    random.shuffle(rows)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "log_id",
        "timestamp",
        "service_name",
        "service_encoded",
        "error_type",
        "severity_label",
        "raw_log",
        "message",
        "source_ip",
        "hour_of_day",
        "is_weekend",
        "message_length",
    ]

    with output_file.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate_dataset()
    print("Dataset generated: data/processed/logs_labeled.csv")