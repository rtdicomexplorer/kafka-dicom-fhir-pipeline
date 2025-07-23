import subprocess
import time
import os
import threading
import signal

# Ensure logs/ directory exists
os.makedirs("logs", exist_ok=True)

services = {
    "Receiver": {
        "cmd": "python dicom_receiver.py",
        "log": "logs/receiver.log"
    },
    "Study Grouper": {
        "cmd": "python consumer_grouped_study_processor.py",
        "log": "logs/grouper.log"
    },
    "FHIR Uploader": {
        "cmd": "python consumer_fhir_uploader.py",
        "log": "logs/uploader.log"
    },
    "DLQ Handler": {
        "cmd": "python consumer_dlq_handler.py",
        "log": "logs/dlq_handler.log"
    }
}

running = True
processes = {}

def start_service_old_stdout_to_log(name, config):
    """Start a subprocess and return the Popen object."""
    log_file = open(config["log"], "a", encoding="utf-8")  # ✅ UTF-8 logs
    print(f"🔹 Starting {name} → logging to {config['log']}")
    return subprocess.Popen(
        config["cmd"],
        shell=True,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

def start_service(name, config):
    print(f"🔹 Starting {name}")
    return subprocess.Popen(
        config["cmd"],
        shell=True
    )



def monitor_service(name, config):
    """Restart the service if it crashes."""
    while running:
        proc = start_service(name, config)
        processes[name] = proc
        proc.wait()
        if running:
            print(f"⚠️  {name} exited. Restarting in 5 seconds...")
            time.sleep(5)

def shutdown(signum=None, frame=None):
    global running
    print("\n🛑 Shutting down all services...")
    running = False
    for name, proc in processes.items():
        print(f"⛔ Terminating {name}...")
        proc.terminate()
    print("📁 Logs saved in ./logs/")
    print("👋 Shutdown complete.")
    exit(0)

# Handle Ctrl+C or kill
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

print("🚀 Starting DICOM-to-FHIR pipeline with auto-restart and UTF-8 logs...")

# Start threads
for name, config in services.items():
    t = threading.Thread(target=monitor_service, args=(name, config), daemon=True)
    t.start()

# Main loop
while True:
    time.sleep(10)
