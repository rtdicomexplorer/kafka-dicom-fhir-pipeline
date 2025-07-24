# batch_send_by_study.py
import os
import json
import time
from collections import defaultdict
from pydicom import dcmread
from dicom_sender import send_dicom_file  # Import function
from kafka import KafkaProducer

STUDY_FOLDER =  "./study_folder/testdata" # r"C:\challenge_testdata\test"
DELAY_BETWEEN_GROUPS = 3  # seconds between studies
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda m: json.dumps(m).encode('utf-8')
)

def group_dicoms_by_study(folder):
    study_map = defaultdict(list)

    for root, _, files in os.walk(folder):
        for f in files:
            if not f.lower().endswith(".dcm"):
                continue
            filepath = os.path.join(root, f)
            try:
                ds = dcmread(filepath, stop_before_pixels=True)
                study_uid = getattr(ds, "StudyInstanceUID", None)
                if study_uid:
                    study_map[study_uid].append(filepath)
            except Exception as e:
                print(f"⚠️ Could not read {f}: {e}")
    return study_map

from datetime import datetime

def send_study_complete_event(producer, study_uid):
    complete_event = {
        "study_uid": study_uid,
        "event_type": "study_complete",
        "timestamp": datetime.utcnow().isoformat()
    }
    producer.send("imaging.raw", complete_event)
    producer.flush()
    print(f"📢 Sent study_complete event for StudyUID: {study_uid}")

def main():
    study_groups = group_dicoms_by_study(STUDY_FOLDER)
    print(f"📦 Found {len(study_groups)} unique studies.")

    for study_uid, files in study_groups.items():
        print(f"\n🧪 Sending Study UID: {study_uid} ({len(files)} files)")
        for f in files:
            send_dicom_file(f)
        print(f"✅ Finished sending study: {study_uid}")

        send_study_complete_event(producer, study_uid)
        time.sleep(DELAY_BETWEEN_GROUPS)

if __name__ == "__main__":
    main()
