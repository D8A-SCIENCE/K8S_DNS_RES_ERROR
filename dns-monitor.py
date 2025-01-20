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
    "http://example.com",
    "http://google.com",
    "http://bing.com",
    "http://yahoo.com"
]

BACKOFF_SECONDS = 180  # 3 minutes
INTERNAL_THREADS = 10
EXTERNAL_THREADS = 5

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
        return (url, True, None)  # URL, success flag, no error
    except Exception as e:
        error_message = f"ERROR: Failed to connect to {url} - {e}"
        log_message(error_message)
        return (url, False, str(e))  # URL, failure flag, error message

def process_urls(urls, num_threads):
    stats["total_attempts"] += len(urls)
    successful_attempts = 0
    errors = []

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_url = {executor.submit(check_connection, url): url for url in urls}
        for future in as_completed(future_to_url):
            url, success, error = future.result()
            if success:
                successful_attempts += 1
            else:
                errors.append((url, error))

    stats["successful_attempts"] += successful_attempts
    stats["errors"].extend(errors)

while True:
    # 10 internal DNS requests
    process_urls([internal_url] * 100, INTERNAL_THREADS)

    # 5 external DNS requests
    process_urls(external_urls, EXTERNAL_THREADS)

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

    time.sleep(BACKOFF_SECONDS)
