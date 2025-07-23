# dicom_receiver.py
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pydicom import dcmread
from kafka import KafkaProducer
import os
import json
from datetime import datetime
import sys
import io

from log_utils import setup_logger

from service_names import RECEIVER
log = setup_logger(RECEIVER, f"{RECEIVER}.log")

# Force UTF-8 output (for Windows terminal support)
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SAVE_DIR = "./received_dicoms"

os.makedirs(SAVE_DIR, exist_ok=True)

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def handle_store(event):
    ds = event.dataset
    ds.file_meta = event.file_meta

    patient_id = getattr(ds, "PatientID", "")

    patient_name_raw = getattr(ds, "PatientName", "")
    # Safely decode to string
    if isinstance(patient_name_raw, bytes):
        patient_name_str = patient_name_raw.decode('utf-8', errors='ignore')
    else:
        patient_name_str = str(patient_name_raw)
    # patient_name = getattr(ds, "PatientName", "")  # This will be a pydicom PersonName object
    # patient_name_str = patient_name.original_string if patient_name else ""  # Convert to string
    patient_sex = getattr(ds, "PatientSex", "")

    sop_instance_uid = ds.SOPInstanceUID
    study_uid = ds.StudyInstanceUID
    series_uid = ds.SeriesInstanceUID
    sop_uid = ds.SOPInstanceUID
    filename = os.path.join(SAVE_DIR, f"{sop_instance_uid}.dcm")

    ds.save_as(filename, write_like_original=False)
    print(f"📥 Received DICOM for Patient {patient_id}, saved to {filename}")
    log.info(f"✅ DICOM receiver started: listen: {11112}")

    kafka_event = {
        "patient_id": patient_id,
        "patient_name": patient_name_str,    # Add patient name string
        "patient_sex": patient_sex,          # Add patient sex
        "study_uid": study_uid,
        "series_uid": series_uid,
        "sop_uid": sop_uid,
        "dicom_file_path": filename,
        "timestamp": datetime.utcnow().isoformat()
    }
    try:

        producer.send("imaging.raw", kafka_event)
        producer.flush()

        log.info(f"📤 Step 3: Sent message to Kafka topic 'imaging.raw'")
        print(f"📤 Step 3: Sent message to Kafka topic 'imaging.raw'")
    except Exception as e:
        print(e)
        log.error("❌ Something went wrong", exc_info=True)

    return 0x0000  # Success status

handlers = [(evt.EVT_C_STORE, handle_store)]

ae = AE(ae_title="RECEIVER_AE")

for context in AllStoragePresentationContexts:
    ae.add_supported_context(context.abstract_syntax)

msg =f"✅ {RECEIVER} started: listen: {11112}"
log.info(msg)
print(msg)
ae.start_server(('0.0.0.0', 11112), evt_handlers=handlers)
