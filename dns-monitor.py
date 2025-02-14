import os
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import psycopg2

# File paths
log_dir = "/sciclone/home/dsmillerrunfol/tmp"
log_file = os.path.join(log_dir, "log")
summary_file = os.path.join(log_dir, "summary")

# Database Configuration
DB_SERVICE = os.getenv("DB_SERVICE", "geoboundaries-postgres-service")
DB_NAME = os.getenv("DB_NAME", "geoboundaries")
DB_USER = os.getenv("DB_USER", "geoboundaries")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = 5432

# Server endpoints
internal_url = "http://internal-dns-test/"
external_urls = [
    "http://www.wm.edu",
    "https://wm.edu",
    "http://google.com",
    "http://bing.com",
    "http://yahoo.com",
    "https://www.planet.com"
]

BACKOFF_SECONDS = 120  # 2 minutes
INTERNAL_ITERATIONS = 1000
CPU_COUNT = 16
external_urls = [
    "http://www.wm.edu",
    "https://wm.edu",
    "http://google.com",
    "http://bing.com",
    "http://yahoo.com",
    "https://www.planet.com"
]

BACKOFF_SECONDS = 120  # 2 minutes
INTERNAL_ITERATIONS = 1000
CPU_COUNT = 16

# Statistics
stats = {"total_attempts": 0, "successful_attempts": 0, "errors": []}
iteration_count = 0
iteration_count = 0

# Ensure directories exist
os.makedirs(log_dir, exist_ok=True)

def load_kubernetes_config():
    try:
        config_file = "/sciclone/geograd/geoBoundaries/.kube/config"
        if os.path.exists(config_file):
            config.load_kube_config(config_file=config_file)
            logging.info(f"Kubernetes configuration loaded from: {config_file}")
        else:
            raise FileNotFoundError(f"Kubeconfig file not found at: {config_file}")
    except Exception as e:
        logging.error(f"Error loading Kubernetes configuration: {e}")
        raise

def log_message(message):
    """Log messages to the specified log file."""
    """Log messages to the specified log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as log:
        log.write(f"[{timestamp}] {message}\n")

def check_connection(url, headers=None):
    """Attempt a connection to the specified URL."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        log_message(f"SUCCESS: Connected to {url}")
        return (url, True, None)  # URL, success flag, no error
    except Exception as e:
        error_message = f"ERROR: Failed to connect to {url} - {e}"
        log_message(error_message)
        return (url, False, str(e))  # URL, failure flag, error message

def process_urls(urls, num_threads, headers=None, delay_between=0.5):
    """Process a list of URLs in parallel, staggering requests."""
    stats["total_attempts"] += len(urls)
    successful_attempts = 0
    errors = []

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for url in urls:
            futures.append(executor.submit(check_connection, url, headers))
            time.sleep(delay_between)  # Space out requests

        for future in futures:
            url, success, error = future.result()
            if success:
                successful_attempts += 1
            else:
                errors.append((url, error))

    stats["successful_attempts"] += successful_attempts
    stats["errors"].extend(errors)

def generate_summary():
    """Generate a summary of the test results and write to the summary file."""
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

    time.sleep(300)  # Wait 5 minutes before the next check
