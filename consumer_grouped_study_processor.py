#consumer_grouped_study_processor.py
from kafka import KafkaConsumer, KafkaProducer
from pydicom import dcmread
from cachetools import TTLCache
import json, time, os, threading
from kafka_utils import run_consumer_loop

from log_utils import setup_logger
from service_names import STUDY_GROUPER
from dotenv import load_dotenv
import os
log = setup_logger(STUDY_GROUPER, f"{STUDY_GROUPER}.log")


load_dotenv(override=True)

bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")




consumer = KafkaConsumer(
    "imaging.raw",
    bootstrap_servers=bootstrap_servers,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="study-grouper",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers,
    value_serializer=lambda m: json.dumps(m).encode('utf-8')
)

study_files = {}
study_cache = TTLCache(maxsize=100, ttl=30)  # TTL to auto-clear if inactive for 10 seconds

txt_log = f"✅ {STUDY_GROUPER}: started"
print(txt_log)
log.info(txt_log)
def process_study(study_uid):
    entries = study_files.pop(study_uid, [])


    if not entries:
        return

    valid_entries = [e for e in entries if os.path.exists(e["dicom_file_path"])]
    if not valid_entries:
        log.warning(f"⚠️ No valid DICOM files for StudyUID: {study_uid}")
        return

    print(f"📦 Grouping complete for StudyUID: {study_uid}, files: {len(valid_entries)}")
    log.info(f"📦 Grouping complete for StudyUID: {study_uid}, files: {len(valid_entries)}")

    first = valid_entries[0]
    patient_id = first["patient_id"]
    patient_name = first.get("patient_name", "")
    patient_sex = first.get("patient_sex", "")
    scan_time = first["timestamp"]
    patient_birthdate = first["patient_birthdate"]
    study_description = first["study_description"]

    instances = []
    for entry in valid_entries:
        # if not os.path.exists(entry["dicom_file_path"]):
        #     print(f"⚠️ Missing file: {entry['dicom_file_path']}")
        #     log.warning(f"⚠️ Missing file: {entry['dicom_file_path']}")
        #     continue
        try:
            ds = dcmread(entry["dicom_file_path"])
        except Exception as e:
            log.error(f"❌ Failed to read DICOM: {entry['dicom_file_path']}", exc_info=True)
            continue
        instances.append({
            "sop_instance_uid": ds.SOPInstanceUID,
            "series_uid": ds.SeriesInstanceUID,
            "modality": ds.Modality
        })

    output = {
        "study_uid": study_uid,
        "study_description":study_description,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_sex": patient_sex,
        "patient_birthdate": patient_birthdate,
        "scan_time": scan_time,
        "modality": instances[0]["modality"] if instances else None,
        "accession_number": getattr(ds, "AccessionNumber", None) if instances else None,
        "instances": instances
    }

    log.debug(f"📦 Grouped study payload: {json.dumps(output, indent=2)}")


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

    event_type =  event.get("event_type") 
    if event_type == 'study_inprogress':
        required_keys = ["study_uid", "dicom_file_path", "timestamp", "patient_id"]
        missing = [k for k in required_keys if k not in event]
        #missing = [k for k in required_keys if k not in event or event[k] in (None, '')]
        if missing:
            log.warning(f"⚠️ {STUDY_GROUPER} Missing keys in message: {missing}")
            return

    study_uid = event.get("study_uid")
    if not study_uid:
        print(f"⚠️ Missing study_uid in message: {event}")
        return

    if event_type == "study_complete":
        print(f"📢 Received study_complete for: {study_uid}")
        log.info(f"📢 Received study_complete for: {study_uid}")
        process_study(study_uid)
        study_cache.pop(study_uid, None)
        return

    # If normal DICOM file message
    study_files.setdefault(study_uid, []).append(event)
    study_cache[study_uid] = time.time()



run_consumer_loop(consumer, handle_message, name=STUDY_GROUPER)
