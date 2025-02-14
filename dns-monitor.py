import os
import time
import requests
import logging
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import psycopg2
from kubernetes import client, config

# Argument Parsing
parser = argparse.ArgumentParser(description="DNS Monitoring Script")
parser.add_argument("d3i_flag", choices=["d3i", "not_d3i"], help="Specify either 'd3i' or 'not_d3i'")
args = parser.parse_args()

# File paths
base_log_dir = "/sciclone/geograd/log"
log_dir = os.path.join(base_log_dir, args.d3i_flag)
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "log")
summary_file = os.path.join(log_dir, "summary")

# Database Configuration
DB_SERVICE = os.getenv("DB_SERVICE", "dns-test-postgres")
DB_NAME = os.getenv("DB_NAME", "dns-test-postgres")
DB_USER = os.getenv("DB_USER", "dns-test-postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = 5432

# Server endpoints
internal_url = "http://internal-dns-test-web/"
external_urls = ["http://www.wm.edu"]

BACKOFF_SECONDS = 120  # 2 minutes
CPU_COUNT = 16

# Statistics
stats = {"total_attempts": 0, "successful_attempts": 0, "errors": []}

# Logging Setup
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
        return "Connected"
    except Exception as e:
        log_message(f"ERROR: Database connection failed - {e}")
        return f"Failed ({e})"

def load_kubernetes_config():
    """Load Kubernetes configuration and check the number of running pods in the 'dsmillerrunfol' namespace."""
    try:
        config_file = "/sciclone/geograd/geoBoundaries/.kube/config"
        namespace = "dsmillerrunfol"  # Your personal namespace

        if os.path.exists(config_file):
            config.load_kube_config(config_file=config_file)
            v1 = client.CoreV1Api()
            pods = v1.list_namespaced_pod(namespace=namespace, watch=False)
            pod_count = len(pods.items)

            log_message(f"SUCCESS: Kubernetes cluster is accessible. Running pods in '{namespace}': {pod_count}")
            return pod_count
        else:
            raise FileNotFoundError(f"Kubeconfig file not found at: {config_file}")
    except Exception as e:
        log_message(f"ERROR: Could not access Kubernetes cluster - {e}")
        return None


def check_connection(url, headers=None):
    """Attempt a connection to the specified URL."""
    try:
        response = requests.get(url, headers=headers, timeout=5)
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

def generate_summary(db_status, pod_count):
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

        summary.write(f"\nDatabase Connection Test: {db_status}\n")
        summary.write(f"Kubernetes Cluster Test: {'Running pods: ' + str(pod_count) if isinstance(pod_count, int) else pod_count}\n")

    stats["errors"].clear()  # Clear errors after summarizing

# Run database and Kubernetes tests
db_status = check_database_connection()
pod_count = load_kubernetes_config()

# Run URL checks
log_message("Starting URL connectivity tests...")
process_urls([internal_url] + external_urls, num_threads=CPU_COUNT)

# Generate summary
generate_summary(db_status, pod_count)
