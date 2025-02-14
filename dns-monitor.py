import os
import time
import requests
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import psycopg2
from kubernetes import client, config

# File paths
log_dir = "/sciclone/home/dsmillerrunfol/tmp"
log_file = os.path.join(log_dir, "log")
summary_file = os.path.join(log_dir, "summary")

# Database Configuration
DB_SERVICE = os.getenv("DB_SERVICE", "dns-test-postgres")
DB_NAME = os.getenv("DB_NAME", "dns-test-postgres")
DB_USER = os.getenv("DB_USER", "dns-test-postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = 5432

# Server endpoints
internal_url = "http://internal-dns-test/"
external_urls = ["http://www.wm.edu"]

BACKOFF_SECONDS = 120  # 2 minutes
INTERNAL_ITERATIONS = 1000
CPU_COUNT = 16

# Statistics
stats = {"total_attempts": 0, "successful_attempts": 0, "errors": []}

# Ensure directories exist
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(filename=log_file, level=logging.INFO, format="%(asctime)s - %(message)s")

def log_message(message):
    """Log messages to the log file and print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    logging.info(log_entry)

def check_database_connection():
    """Check if the database can be connected to."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_SERVICE,
            port=DB_PORT
        )
        conn.close()
        log_message("SUCCESS: Connected to the database.")
        return True
    except Exception as e:
        log_message(f"ERROR: Database connection failed - {e}")
        return False

def load_kubernetes_config():
    """Load Kubernetes configuration and check the number of running pods."""
    try:
        config_file = "/sciclone/geograd/geoBoundaries/.kube/config"
        if os.path.exists(config_file):
            config.load_kube_config(config_file=config_file)
            v1 = client.CoreV1Api()
            pods = v1.list_pod_for_all_namespaces(watch=False)
            pod_count = len(pods.items)
            log_message(f"SUCCESS: Kubernetes cluster is accessible. Running pods: {pod_count}")
            return pod_count
        else:
            raise FileNotFoundError(f"Kubeconfig file not found at: {config_file}")
    except Exception as e:
        log_message(f"ERROR: Could not access Kubernetes cluster - {e}")
        return None

def check_connection(url, headers=None):
    """Attempt a connection to the specified URL."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        log_message(f"SUCCESS: Connected to {url}")
        return url, True, None
    except Exception as e:
        error_message = f"ERROR: Failed to connect to {url} - {e}"
        log_message(error_message)
        return url, False, str(e)

def process_urls(urls, num_threads, headers=None, delay_between=0.5):
    """Process a list of URLs in parallel, staggering requests."""
    stats["total_attempts"] += len(urls)
    successful_attempts = 0
    errors = []

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for url in urls:
            futures.append(executor.submit(check_connection, url, headers))
            time.sleep(delay_between)

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
        success_rate = (stats["successful_attempts"] / stats["total_attempts"] * 100) if stats["total_attempts"] > 0 else 0
        common_errors = {error: stats["errors"].count(error) for error in set(stats["errors"])}
        most_recent_test = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        summary.write(f"Most Recent Tests: {most_recent_test}\n")
        summary.write(f"Total Attempts: {stats['total_attempts']}\n")
        summary.write(f"Successful Attempts: {stats['successful_attempts']}\n")
        summary.write(f"Success Rate: {success_rate:.2f}%\n")
        summary.write(f"Common Errors:\n")
        for error, count in common_errors.items():
            summary.write(f"  {error}: {count} occurrences\n")

        # Append database and Kubernetes test results
        db_status = "Connected" if check_database_connection() else "Failed"
        pod_count = load_kubernetes_config()
        k8s_status = f"Running pods: {pod_count}" if pod_count is not None else "Failed to retrieve pod count"

        summary.write(f"\nDatabase Connection Test: {db_status}\n")
        summary.write(f"Kubernetes Cluster Test: {k8s_status}\n")

    stats["errors"].clear()  # Clear errors after summarizing

# Run database and Kubernetes tests
check_database_connection()
load_kubernetes_config()

# Generate summary
generate_summary()
