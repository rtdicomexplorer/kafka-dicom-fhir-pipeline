import subprocess
import time
import os
import threading
import signal
from flask import Flask, jsonify, abort, Response, request
from service_names import DLQ_HANDLER,FHIR_UPLOADER,RECEIVER,STUDY_GROUPER

# Ensure logs/ directory exists
os.makedirs("logs", exist_ok=True)

services = {
    RECEIVER: {
        "cmd": "python dicom_receiver.py",
        "log": f"logs/{RECEIVER}.log"
    },
    STUDY_GROUPER: {
        "cmd": "python consumer_grouped_study_processor.py",
        "log": f"logs/{STUDY_GROUPER}.log"
    },
    FHIR_UPLOADER: {
        "cmd": "python consumer_fhir_uploader.py",
        "log": f"logs/{FHIR_UPLOADER}.log"
    },
    DLQ_HANDLER: {
        "cmd": "python consumer_dlq_handler.py",
        "log": f"logs/{DLQ_HANDLER}.log"
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


def check_status():
    status = {}
    for name, proc in processes.items():
        retcode = proc.poll()  # None if still running
        status[name] = "running" if retcode is None else f"stopped (exit code {retcode})"
    return status


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

# Flask app setup
app = Flask(__name__)

@app.route("/status")
def status_endpoint():
    return jsonify(check_status())


@app.route("/services")
def list_services():
    status = check_status()
    return jsonify({
        name: {
            "status": status.get(name, "unknown"),
            "cmd": config["cmd"],
            "log": config["log"]
        }
        for name, config in services.items()
    })

@app.route("/logs/<service_name>")
def get_logs(service_name):
    if service_name not in services:
        abort(404, description="Service not found")
    try:
        with open(services[service_name]["log"], "r", encoding="utf-8") as f:
            logs = f.read()
        return Response(logs, mimetype="text/plain")
    except Exception as e:
        abort(500, description=str(e))

@app.route("/restart/<service_name>", methods=["POST"])
def restart_service(service_name):
    if service_name not in services:
        abort(404, description="Service not found")
    proc = processes.get(service_name)
    if proc:
        proc.terminate()
        return jsonify({"message": f"{service_name} restarting"}), 202
    else:
        return jsonify({"message": f"{service_name} not running"}), 400

@app.route("/shutdown", methods=["POST"])
def shutdown_server():
    def shutdown_thread():
        time.sleep(1)
        shutdown()
    threading.Thread(target=shutdown_thread).start()
    return jsonify({"message": "Shutdown initiated"}), 202






def start_http_server():
    app.run(host="0.0.0.0", port=8085, debug=False, use_reloader=False)



def main():
    global running

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("🚀 Starting DICOM-to-FHIR pipeline with auto-restart and UTF-8 logs...")

    # Start service monitor threads
    for name, config in services.items():
        t = threading.Thread(target=monitor_service, args=(name, config), daemon=True)
        t.start()

    # Start Flask HTTP server thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    print("🌐 HTTP status server started at http://localhost:8085/status")

    # Main loop to keep script running
    while True:
        time.sleep(10)



if __name__ == "__main__":
    main()

# # Handle Ctrl+C or kill
# signal.signal(signal.SIGINT, shutdown)
# signal.signal(signal.SIGTERM, shutdown)

# print("🚀 Starting DICOM-to-FHIR pipeline with auto-restart and UTF-8 logs...")

# # Start threads
# for name, config in services.items():
#     t = threading.Thread(target=monitor_service, args=(name, config), daemon=True)
#     t.start()




# # Main loop
# while True:
#     time.sleep(10)
