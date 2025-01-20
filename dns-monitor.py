import os
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# File paths
log_dir = "/sciclone/geograd/K8S_DNS_RES_ERROR"
log_file = os.path.join(log_dir, "log")
summary_file = os.path.join(log_dir, "summary")

# Server endpoints
internal_url = "http://internal-dns-test/"
external_urls = [
    "http://www.wm.edu",
    "https://wm.edu",
    "http://google.com",
    "http://bing.com",
    "http://yahoo.com",
    "https://api.planet.com/basemaps/v1/mosaics"
]

BACKOFF_SECONDS = 120  # in seconds
INTERNAL_ITERATIONS = 1000
CPU_COUNT = 16

# Statistics
stats = {"total_attempts": 0, "successful_attempts": 0, "errors": []}
iteration_count = 0

# Ensure directories exist
os.makedirs(log_dir, exist_ok=True)

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as log:
        log.write(f"[{timestamp}] {message}\n")

def check_connection(url, headers=None):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        log_message(f"SUCCESS: Connected to {url}")
        return (url, True, None)  # URL, success flag, no error
    except Exception as e:
        error_message = f"ERROR: Failed to connect to {url} - {e}"
        log_message(error_message)
        return (url, False, str(e))  # URL, failure flag, error message

def process_urls(urls, num_threads, headers=None):
    stats["total_attempts"] += len(urls)
    successful_attempts = 0
    errors = []

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_url = {executor.submit(check_connection, url, headers): url for url in urls}
        for future in as_completed(future_to_url):
            url, success, error = future.result()
            if success:
                successful_attempts += 1
            else:
                errors.append((url, error))

    stats["successful_attempts"] += successful_attempts
    stats["errors"].extend(errors)

def generate_summary():
    with open(summary_file, "w") as summary:
        success_rate = stats["successful_attempts"] / stats["total_attempts"] * 100 if stats["total_attempts"] > 0 else 0
        common_errors = {error: stats["errors"].count(error) for error in set(stats["errors"])}
        most_recent_test = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary.write(f"Most Recent Tests: {most_recent_test}\n")
        summary.write(f"Total Attempts: {stats['total_attempts']}\n")
        summary.write(f"Successful Attempts: {stats['successful_attempts']}\n")
        summary.write(f"Success Rate: {success_rate:.2f}%\n")
        summary.write(f"Common Errors:\n")
        for error, count in common_errors.items():
            summary.write(f"  {error}: {count} occurrences\n")
    stats["errors"].clear()  # Clear errors after summarizing

# Headers for the requests
headers = {
    "User-Agent": "DNS-Test-Script/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

while True:
    iteration_count += 1

    # 10 internal DNS requests
    process_urls([internal_url] * INTERNAL_ITERATIONS, CPU_COUNT, headers)

    # 5 external DNS requests
    process_urls(external_urls, CPU_COUNT, headers)

    generate_summary()

    time.sleep(BACKOFF_SECONDS)
