import os
import time
import requests
from datetime import datetime

# File paths
log_dir = "/sciclone/geograd/K8S_DNS_RES_ERROR"
log_file = os.path.join(log_dir, "log")
summary_file = os.path.join(log_dir, "summary")

# Server endpoints
internal_url = "http://internal-dns-test/"
external_url = "http://www.wm.edu"

# Statistics
stats = {"total_attempts": 0, "successful_attempts": 0, "errors": []}

# Ensure directories exist
os.makedirs(log_dir, exist_ok=True)

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as log:
        log.write(f"[{timestamp}] {message}\n")

def check_connection(url):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        log_message(f"SUCCESS: Connected to {url}")
        return True
    except Exception as e:
        error_message = f"ERROR: Failed to connect to {url} - {e}"
        log_message(error_message)
        stats["errors"].append((url, str(e)))
        return False

while True:
    stats["total_attempts"] += 1
    internal_success = check_connection(internal_url)
    external_success = check_connection(external_url)

    if internal_success and external_success:
        stats["successful_attempts"] += 1

    # Generate summary once per hour
    if datetime.now().minute == 0:
        with open(summary_file, "w") as summary:
            success_rate = stats["successful_attempts"] / stats["total_attempts"] * 100
            common_errors = {error: stats["errors"].count(error) for error in set(stats["errors"])}
            summary.write(f"Total Attempts: {stats['total_attempts']}\n")
            summary.write(f"Successful Attempts: {stats['successful_attempts']}\n")
            summary.write(f"Success Rate: {success_rate:.2f}%\n")
            summary.write(f"Common Errors:\n")
            for error, count in common_errors.items():
                summary.write(f"  {error}: {count} occurrences\n")
        stats["errors"].clear()  # Clear errors after summarizing

    time.sleep(300)  # Wait 5 minutes before the next check
