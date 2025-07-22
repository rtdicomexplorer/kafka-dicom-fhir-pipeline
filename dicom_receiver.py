# dicom_receiver.py
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pydicom import dcmread
from kafka import KafkaProducer
import os
import json
from datetime import datetime

SAVE_DIR = "./received_dicoms"

os.makedirs(SAVE_DIR, exist_ok=True)

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def handle_store(event):
    ds = event.dataset
    ds.file_meta = event.file_meta

    patient_id = ds.PatientID
    sop_instance_uid = ds.SOPInstanceUID
    filename = os.path.join(SAVE_DIR, f"{sop_instance_uid}.dcm")

    ds.save_as(filename, write_like_original=False)
    print(f"📥 Received DICOM for Patient {patient_id}, saved to {filename}")

    kafka_event = {
        "patient_id": patient_id,
        "dicom_file_path": filename,
        "timestamp": datetime.utcnow().isoformat()
    }
    producer.send("imaging.raw", kafka_event)
    producer.flush()
    print(f"📤 Step 3: Sent message to Kafka topic 'imaging.raw': {kafka_event}")

    return 0x0000  # Success status

handlers = [(evt.EVT_C_STORE, handle_store)]

ae = AE()
for context in AllStoragePresentationContexts:
    ae.add_supported_context(context.abstract_syntax)

print(f"📤 DICOM receiver: started: {11112}")
ae.start_server(('0.0.0.0', 11112), evt_handlers=handlers)
