#run_pipeline.py
import subprocess
import time
import os
import threading
import signal
from flask import Flask, jsonify, abort, Response, request,redirect,render_template_string
from service_names import DLQ_HANDLER,FHIR_UPLOADER,RECEIVER,STUDY_GROUPER
from dotenv import load_dotenv
os.makedirs("logs", exist_ok=True)
load_dotenv(override=True)


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
service_should_restart = {name: True for name in services}  # Control auto

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
    while running:
        if not service_should_restart.get(name, True):
            # Service is stopped manually, do not restart
            time.sleep(1)
            continue
        proc = start_service(name, config)
        processes[name] = proc
        proc.wait()
        if running and service_should_restart.get(name, True):
            print(f"⚠️  {name} exited. Restarting in 5 seconds...")
            time.sleep(5)


def check_status():
    status = {}
    for name, proc in processes.items():
        retcode = proc.poll()  # None if still running
        status[name] = "running" if retcode is None else f"stopped (exit code {retcode})"
    # Also include services not yet started
    for name in services.keys():
        if name not in status:
            status[name] = "stopped"
    return status


def shutdown(signum=None, frame=None):
    global running
    running = False
    for name, proc in processes.items():
        print(f"⛔ Terminating {name}...")
        service_should_restart[name] = False
        proc.terminate()
   
    print("👋 Shutdown complete.")
    exit(0)

# Flask app setup
app = Flask(__name__)


# Add this new route to redirect '/' to '/dashboard'
@app.route("/")
def home():
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    status = check_status()
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>DICOM Pipeline Dashboard</title>
<style>
  body { font-family: Arial, sans-serif; margin: 20px; background: #f0f2f5; }
  table { border-collapse: collapse; width: 100%; max-width: 900px; }
  th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
  th { background-color: #4CAF50; color: white; }
  tr:nth-child(even) { background-color: #fafafa; }
  button { padding: 6px 12px; margin-right: 5px; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  #logModal {
    display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%;
    overflow: auto; background-color: rgba(0,0,0,0.5);
  }
  #logContent {
    background-color: #fff; margin: 10% auto; padding: 20px; border: 1px solid #888;
    width: 80%; max-height: 70vh; overflow-y: scroll; white-space: pre-wrap; font-family: monospace;
  }
  #closeLogBtn { float: right; cursor: pointer; font-size: 20px; font-weight: bold; }
</style>
</head>
<body>
  <h1>DICOM Pipeline Dashboard</h1>
  <table>
    <thead>
      <tr><th>Service</th><th>Status</th><th>Actions</th><th>Log File</th></tr>
    </thead>
    <tbody>
    {% for name, config in services.items() %}
      <tr>
        <td>{{ name }}</td>
        <td id="{{ name }}-status">{{ status[name] }}</td>
        <td>
          <button onclick="startService('{{ name }}')" id="{{ name }}-start" {% if status[name] == 'running' %}disabled{% endif %}>Start</button>
          <button onclick="stopService('{{ name }}')" id="{{ name }}-stop" {% if status[name] != 'running' %}disabled{% endif %}>Stop</button>
          <button onclick="restartService('{{ name }}')" id="{{ name }}-restart" {% if status[name] != 'running' %}disabled{% endif %}>Restart</button>
          <button onclick="showLogs('{{ name }}')">Logs</button>
        </td>
        <td>{{ config['log'] }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <div id="logModal">
    <div id="logContent">
      <span id="closeLogBtn" onclick="closeLogs()">&times;</span>
      <h2>Logs for <span id="logServiceName"></span></h2>
      <pre id="logText">Loading...</pre>
    </div>
  </div>

<script>
  async function refreshStatus() {
    const res = await fetch('/status');
    const data = await res.json();
    for (const [name, state] of Object.entries(data)) {
      document.getElementById(name + '-status').innerText = state;
      document.getElementById(name + '-start').disabled = (state === 'running');
      document.getElementById(name + '-stop').disabled = (state !== 'running');
      document.getElementById(name + '-restart').disabled = (state !== 'running');
    }
  }
  setInterval(refreshStatus, 3000);
  window.onload = refreshStatus;

  async function startService(name) {
    const res = await fetch(`/start/${name}`, {method: 'POST'});
    if (res.ok) {
      alert(`Started ${name}`);
      refreshStatus();
    } else {
      alert(`Failed to start ${name}`);
    }
  }

  async function stopService(name) {
    const res = await fetch(`/stop/${name}`, {method: 'POST'});
    if (res.ok) {
      alert(`Stopped ${name}`);
      refreshStatus();
    } else {
      alert(`Failed to stop ${name}`);
    }
  }

  async function restartService(name) {
    const res = await fetch(`/restart/${name}`, {method: 'POST'});
    if (res.ok) {
      alert(`Restarting ${name}`);
      refreshStatus();
    } else {
      alert(`Failed to restart ${name}`);
    }
  }

  async function showLogs(name) {
    document.getElementById('logModal').style.display = 'block';
    document.getElementById('logServiceName').innerText = name;
    document.getElementById('logText').innerText = 'Loading...';
    try {
      const res = await fetch(`/logs/${name}`);
      if (!res.ok) {
        document.getElementById('logText').innerText = `Failed to load logs: ${res.statusText}`;
        return;
      }
      const text = await res.text();
      document.getElementById('logText').innerText = text || '(No logs)';
    } catch(e) {
      document.getElementById('logText').innerText = `Error loading logs: ${e.message}`;
    }
  }

  function closeLogs() {
    document.getElementById('logModal').style.display = 'none';
  }
</script>
</body>
</html>
"""
    return render_template_string(html, services=services, status=status)



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

@app.route("/start/<service_name>", methods=["POST"])
def start_service_endpoint(service_name):
    if service_name not in services:
        abort(404, description="Service not found")
    proc = processes.get(service_name)
    if proc and proc.poll() is None:
        return jsonify({"message": f"{service_name} already running"}), 400
    service_should_restart[service_name] = True
    new_proc = start_service(service_name, services[service_name])
    processes[service_name] = new_proc
    return jsonify({"message": f"{service_name} started"}), 202


@app.route("/stop/<service_name>", methods=["POST"])
def stop_service_endpoint(service_name):
    if service_name not in services:
        abort(404, description="Service not found")
    proc = processes.get(service_name)
    if proc and proc.poll() is None:
        service_should_restart[service_name] = False
        proc.terminate()
        return jsonify({"message": f"{service_name} stopping"}), 202
    else:
        return jsonify({"message": f"{service_name} is not running"}), 400




@app.route("/restart/<service_name>", methods=["POST"])
def restart_service(service_name):
    if service_name not in services:
        abort(404, description="Service not found")
    proc = processes.get(service_name)
    service_should_restart[service_name] = True
    if proc and proc.poll() is None:
        proc.terminate()
    return jsonify({"message": f"{service_name} restarting"}), 202

@app.route("/shutdown", methods=["POST"])
def shutdown_server():
    def shutdown_thread():
        time.sleep(1)
        shutdown()
    threading.Thread(target=shutdown_thread).start()
    return jsonify({"message": "Shutdown initiated"}), 202




FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

def start_http_server():
    app.run(host=FLASK_HOST, port=FLASK_PORT,debug=False, use_reloader=False)



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
    print(f"🌐 Dashboard at http://{FLASK_HOST}:{FLASK_PORT}")

    # Main loop to keep script running
    while True:
        time.sleep(10)



if __name__ == "__main__":
    main()

