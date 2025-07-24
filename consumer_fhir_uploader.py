#consuumer_fhir_uploader.py
from kafka import KafkaConsumer
import json, os, requests
from kafka_utils import run_consumer_loop
import uuid
from log_utils import setup_logger

from service_names import FHIR_UPLOADER
from utils import convert_dicom_date
from dotenv import load_dotenv
import os
log = setup_logger(FHIR_UPLOADER, f"{FHIR_UPLOADER}.log")
FHIR_SERVER = "http://localhost:8080/fhir"
load_dotenv(override=True)

bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

consumer = KafkaConsumer(
    "imaging.study.ready",
    bootstrap_servers=bootstrap_servers,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="fhir-uploader-group",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
msg =f"✅ {FHIR_UPLOADER}: started'"
log.info(msg)
print(msg)
print("👂 Waiting for messages on topic 'imaging.study.ready'...")

def parse_patient_name(name_str):
    parts = name_str.split("^")
    return {
        "family": parts[0] if len(parts) > 0 else "Unknown",
        "given": [parts[1]] if len(parts) > 1 else ["Unknown"]
    }

patient_gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}

def handle_message(msg):
    study = msg.value

    # ✅ Validate required top-level fields
    required_fields = ["study_uid", "patient_id", "scan_time", "instances"]
    missing = [f for f in required_fields if f not in study]
    if missing:
        log.warning(f"⚠️ {FHIR_UPLOADER} Missing required fields in study: {missing}")
        return

     # Prepare identifiers and UUID for linking
    patient_identifier_value = study.get("accession_number") or f"{study['patient_id']}"
    temp_patient_uuid = f"urn:uuid:{uuid.uuid4()}"

    # Parse patient name and gender
    patient_name_str = study.get("patient_name", "Test^Patient")
    patient_name = parse_patient_name(patient_name_str)
    patient_gender = patient_gender_map.get(study.get("patient_sex", "").upper(), None)
    birth_date = convert_dicom_date(study.get("patient_birthdate", ""))
    study_description = study.get("study_description","")

    # Build series map for ImagingStudy
    series_map = {}
    instances = study["instances"]
    for inst in instances:
            sid = inst["series_uid"]
            if sid not in series_map:
                series_map[sid] = {
                    "uid": sid,
                    "modality": {
                        "system": "http://dicom.nema.org/resources/ontology/DCM",
                        "code": inst["modality"]
                    },
                    "instance": []
                }
            series_map[sid]["instance"].append({
                "uid": inst["sop_instance_uid"]
            })

            # Build Patient resource without fixed ID


    patient_resource = {
            "resourceType": "Patient",
            "identifier": [{
                "system": "http://hospital.smartcare.org/patients",
                "value": patient_identifier_value
            }],
            "name": [{
                "use": "official",
                "family": patient_name["family"],
                "given": patient_name["given"]
            }]
        }
    if patient_gender:
            patient_resource["gender"] = patient_gender
    
    if birth_date:
        patient_resource["birthDate"] = birth_date
    # Build ImagingStudy resource referencing Patient by UUID
    imaging_study = {
        "resourceType": "ImagingStudy",
        "subject": {"reference": temp_patient_uuid},
        "started": study["scan_time"],
        "identifier": [{
            "system": "urn:dicom:uid",
            "value": study["study_uid"]
        }],
        "modality": [{
        "system": "http://dicom.nema.org/resources/ontology/DCM",
        "code": instances[0]["modality"]
                }],
        "description": f"{instances[0]['modality']} imaging study",
        "series": list(series_map.values())
        }

    if study_description:
        imaging_study["description"] = study_description

            # Build transaction Bundle
    bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": temp_patient_uuid,
                    "resource": patient_resource,
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    }
                },
                {
                    "resource": imaging_study,
                    "request": {
                        "method": "POST",
                        "url": "ImagingStudy"
                    }
                }
            ]
        }

    os.makedirs("bundles", exist_ok=True)
    with open(f"bundles/imagingstudy_bundle_{study['study_uid']}.json", "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    log.info(f"📤 Sending ImagingStudy bundle for {study['study_uid']}")
    print(f"📤 Sending ImagingStudy bundle for {study['study_uid']}")

    try:
        res = requests.post(FHIR_SERVER, json=bundle, timeout=10)
        if res.status_code in [200, 201]:
            log.info(f"✅ Uploaded to FHIR successfully: ImagingStudy bundle for {study['study_uid']}")
            print("✅ Uploaded to FHIR")
        else:
            log.warning(f"❌ Upload failed ({res.status_code}): {res.text}")
            print(f"❌ Upload failed ({res.status_code}): {res.text}")
    except requests.RequestException as e:
        log.error("❌ Error posting to FHIR server, check if the server is online", exc_info=True)
        print(f"❌ Error posting to FHIR server, check if the server is online")


run_consumer_loop(consumer, handle_message, name=FHIR_UPLOADER)
