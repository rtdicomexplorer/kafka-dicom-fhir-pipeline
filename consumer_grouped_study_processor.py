import os
import json
import time
import threading
from kafka import KafkaConsumer, KafkaProducer
from pydicom import dcmread
from cachetools import TTLCache
from threading import Lock

lock = Lock()

# Kafka setup
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

# Store incoming files grouped by StudyInstanceUID
study_files = {}
study_cache = TTLCache(maxsize=100, ttl=10)  # TTL to auto-clear if inactive for 10 seconds
print("✅ consumer_grouped_study_processor: started'")
def process_study(study_uid):
    entries = study_files.pop(study_uid, [])
    print(f"📦 Grouping complete for StudyUID: {study_uid}, files: {len(entries)}")

    if not entries:
        return

    # Create simplified metadata
    first = entries[0]
    patient_id = first["patient_id"]
    patient_name = first.get("patient_name", "")
    patient_sex = first.get("patient_sex", "")
    scan_time = first["timestamp"]

    instances = []
    for entry in entries:

        if not os.path.exists(entry["dicom_file_path"]):
            print(f"⚠️ Missing file: {entry['dicom_file_path']}")
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
            "patient_name": patient_name,   # Pass along patient_name
            "patient_sex": patient_sex,     # Pass along patient_sex
            "scan_time": scan_time,
            "modality": ds.Modality,
            "accession_number": getattr(ds, "AccessionNumber", None),
            "instances": instances
        }

    print(f"Output sent to consumer_fhir_uploader {output}")
    # Send grouped study to next topic
    producer.send("imaging.study.ready", output)
    producer.flush()
    print(f"🚀 Sent grouped study to 'imaging.study.ready': {study_uid}")

# Background cleaner thread
def watch_expired_studies():
    while True:
        with lock:
            for study_uid in list(study_cache.keys()):
                if study_uid not in study_files:
                    continue
                process_study(study_uid)
                study_cache.pop(study_uid, None)
        time.sleep(2)


threading.Thread(target=watch_expired_studies, daemon=True).start()

print("👂 Listening for DICOM file metadata on 'imaging.raw'...")
for msg in consumer:
    event = msg.value

    if "study_uid" not in event:
        print(f"⚠️ Skipping message without 'study_uid': {event}")
        continue
    study_uid = event["study_uid"]

    if study_uid not in study_files:
        study_files[study_uid] = []
    study_files[study_uid].append(event)

    # Refresh cache TTL for this study
    study_cache[study_uid] = time.time()
