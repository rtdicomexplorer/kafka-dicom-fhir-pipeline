# dicom_receiver.py
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pydicom import dcmread
from kafka import KafkaProducer
import os
import json
from datetime import datetime
from log_utils import setup_logger

from service_names import RECEIVER
from dotenv import load_dotenv
import os

log = setup_logger(RECEIVER, f"{RECEIVER}.log")


SAVE_DIR = "./received_dicoms"

os.makedirs(SAVE_DIR, exist_ok=True)

load_dotenv(override=True)

AE_TITLE = os.getenv("AETITLE", "RECEIVER_AE")
AE_PORT = int(os.getenv("AEPORT", "11112"))

bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def handle_store(event):
    try:
        ds = event.dataset
        ds.file_meta = event.file_meta
    except Exception as e:
        log.error("❌ Failed to parse incoming DICOM dataset", exc_info=True)
        return 0xA700  # Processing failure

    try:
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
        study_description = getattr(ds, "StudyDescription", "")
        #filename = os.path.join(SAVE_DIR, f"{sop_instance_uid}.dcm")
        filename = os.path.join(SAVE_DIR, study_uid, f"{sop_instance_uid}.dcm")
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        ds.save_as(filename, write_like_original=False)
        kafka_event = {
            "event_type": "study_inprogress",
            "patient_id": patient_id,
            "patient_name": patient_name_str,    # Add patient name string
            "patient_sex": patient_sex,          # Add patient sex
            "study_uid": study_uid,
            "series_uid": series_uid,
            "sop_uid": sop_instance_uid,
            "dicom_file_path": filename,
            "study_description": study_description,
            "patient_birthdate":getattr(ds, "PatientBirthDate", ""),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        log.error("❌ Something went wrong", exc_info=True)
        return 0xC210  # Processing failure

    try:
        log.info(f"📤 Step 3: Sent message to Kafka topic 'imaging.raw'")
        producer.send("imaging.raw", kafka_event)
        producer.flush()


    except Exception as e:
        log.error("❌ Something went wrong", exc_info=True)
        return 0xC210  # Processing failure

    return 0x0000  # Success status

handlers = [(evt.EVT_C_STORE, handle_store)]

ae = AE()

for context in AllStoragePresentationContexts:
    ae.add_supported_context(context.abstract_syntax)

msg =f"✅ {RECEIVER} started: listen: {AE_PORT}"
log.info(msg)
ae.start_server(ae_title=AE_TITLE, address=('0.0.0.0', AE_PORT), block=True, evt_handlers=handlers)
