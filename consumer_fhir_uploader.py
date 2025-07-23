from kafka import KafkaConsumer
import json, os, requests
from kafka_utils import run_consumer_loop
import uuid
from log_utils import setup_logger
log = setup_logger("consumer_fhir_uploader", "consumer_fhir_uploader.log")
FHIR_SERVER = "http://localhost:8080/fhir"

consumer = KafkaConsumer(
    "imaging.study.ready",
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="fhir-uploader-group",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
msg ="✅ consumer_fhir_uploader: started'"
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
     # Prepare identifiers and UUID for linking
    patient_identifier_value = study.get("accession_number") or f"{study['patient_id']}"
    temp_patient_uuid = f"urn:uuid:{uuid.uuid4()}"

    # Parse patient name and gender
    patient_name_str = study.get("patient_name", "Test^Patient")
    patient_name = parse_patient_name(patient_name_str)
    patient_gender = patient_gender_map.get(study.get("patient_sex", "").upper(), None)

    # Build series map for ImagingStudy
    series_map = {}
    for inst in study["instances"]:
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
     # Build ImagingStudy resource referencing Patient by UUID
    imaging_study = {
        "resourceType": "ImagingStudy",
        "subject": {"reference": temp_patient_uuid},
        "started": study["scan_time"],
        "identifier": [{
            "system": "urn:dicom:uid",
            "value": study["study_uid"]
        }],
        "series": list(series_map.values())
    }

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
    res = requests.post(FHIR_SERVER, json=bundle)
    if res.status_code in [200, 201]:
        print("✅ Uploaded to FHIR")
        log.info(f"✅ Sending ImagingStudy bundle for {study['study_uid']}")
    else:
        print(f"❌ Upload failed ({res.status_code}): {res.text}")
        log.info(f"❌ Upload failed ({res.status_code}): {res.text}")

run_consumer_loop(consumer, handle_message, name="FHIR Uploader")
