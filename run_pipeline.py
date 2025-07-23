import subprocess
import time

services = {
    "Receiver": "python dicom_receiver.py",
    "Study Grouper": "python consumer_grouped_study_processor.py",
    "FHIR Uploader": "python consumer_fhir_uploader.py",
    "DLQ Handler": "python consumer_dlq_handler.py"
}

processes = {}

try:
    print("🚀 Starting DICOM-to-FHIR pipeline...")

    for name, command in services.items():
        print(f"🔹 Launching {name}...")
        processes[name] = subprocess.Popen(command, shell=True)

    print("✅ All services started. Press Ctrl+C to stop.")

    while True:
        time.sleep(5)

except KeyboardInterrupt:
    print("\n🛑 Stopping all services...")
    for name, proc in processes.items():
        print(f"⛔ Terminating {name}...")
        proc.terminate()
    print("👋 Shutdown complete.")
