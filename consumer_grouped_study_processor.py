from kafka import KafkaConsumer, KafkaProducer
from pydicom import dcmread
from cachetools import TTLCache
import json, time, os, threading
from kafka_utils import run_consumer_loop

from log_utils import setup_logger
from service_names import STUDY_GROUPER

log = setup_logger(STUDY_GROUPER, f"{STUDY_GROUPER}.log")






consumer = KafkaConsumer(
    "imaging.raw",
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="study-grouper",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda m: json.dumps(m).encode('utf-8')
)

study_files = {}
study_cache = TTLCache(maxsize=100, ttl=30)  # TTL to auto-clear if inactive for 10 seconds

txt_log = f"✅ {STUDY_GROUPER}: started"
print(txt_log)
log.info(txt_log)
def process_study(study_uid):
    entries = study_files.pop(study_uid, [])
    print(f"📦 Grouping complete for StudyUID: {study_uid}, files: {len(entries)}")
    log.info(f"📦 Grouping complete for StudyUID: {study_uid}, files: {len(entries)}")

    if not entries:
        return

    first = entries[0]
    patient_id = first["patient_id"]
    patient_name = first.get("patient_name", "")
    patient_sex = first.get("patient_sex", "")
    scan_time = first["timestamp"]

    instances = []
    for entry in entries:
        if not os.path.exists(entry["dicom_file_path"]):
            print(f"⚠️ Missing file: {entry['dicom_file_path']}")
            log.warning(f"⚠️ Missing file: {entry['dicom_file_path']}")
            continue

        ds = dcmread(entry["dicom_file_path"])
        instances.append({
            "sop_instance_uid": ds.SOPInstanceUID,
            "series_uid": ds.SeriesInstanceUID,
            "modality": ds.Modality
        })

    output = {
        "study_uid": study_uid,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_sex": patient_sex,
        "scan_time": scan_time,
        "modality": instances[0]["modality"] if instances else None,
        "accession_number": getattr(ds, "AccessionNumber", None) if instances else None,
        "instances": instances
    }

    try:
        producer.send("imaging.study.ready", output)
        producer.flush()
        print(f"🚀 Sent grouped study to 'imaging.study.ready': {study_uid}")
        log.info(f"🚀 Sent grouped study to 'imaging.study.ready': {study_uid}")
    except Exception as e:
        print(f"Kafka produce error: {e}")
        log.error(f"❌ Sent grouped study to 'imaging.study.ready': {study_uid}", exc_info=True)

def handle_message(msg):
    event = msg.value
    study_uid = event.get("study_uid")
    if not study_uid:
        print(f"⚠️ Missing study_uid in message: {event}")
        return

    if event.get("event_type") == "study_complete":
        print(f"📢 Received study_complete for: {study_uid}")
        log.info(f"📢 Received study_complete for: {study_uid}")
        process_study(study_uid)
        study_cache.pop(study_uid, None)
        return

    # If normal DICOM file message
    study_files.setdefault(study_uid, []).append(event)
    study_cache[study_uid] = time.time()



run_consumer_loop(consumer, handle_message, name=STUDY_GROUPER)
