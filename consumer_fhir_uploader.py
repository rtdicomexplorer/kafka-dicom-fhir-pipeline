import uuid
import json
import os
import requests
from kafka import KafkaConsumer,KafkaProducer
import time


# ✅ Summary of Changes
# Feature	Status
# Retry on failure	✅ 3 attempts with 5s delay
# DLQ support	✅ Kafka topic "imaging.failed"
# Patient ID from DICOM	✅ Name, sex, accession number included
# Bundle saving	✅ Stored under ./bundles/



MAX_RETRIES = 3
RETRY_DELAY_SEC = 5
FHIR_SERVER = "http://localhost:8080/fhir"  # Your FHIR server URL
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda m: json.dumps(m).encode('utf-8')
)

dlq_producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda m: json.dumps(m).encode('utf-8')
)

consumer = KafkaConsumer(
    "imaging.study.ready",
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="fhir-uploader-group",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("✅ consumer_fhir_uploader: started'")
print("👂 Waiting for messages on topic 'imaging.study.ready'...")

def parse_patient_name(name_str):
    parts = name_str.split("^")
    return {
        "family": parts[0] if len(parts) > 0 else "Unknown",
        "given": [parts[1]] if len(parts) > 1 else ["Unknown"]
    }

patient_gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}

for msg in consumer:
    study = msg.value
    for attempt in range(MAX_RETRIES):

        try:

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

            # Save bundle to disk
            os.makedirs("bundles", exist_ok=True)
            bundle_filename = f"bundles/imagingstudy_bundle_{study['study_uid']}.json"
            with open(bundle_filename, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2)
            print(f"💾 Saved FHIR bundle to: {bundle_filename}")

            # POST the bundle to your FHIR server
            print(f"📦 Sending ImagingStudy bundle for Study UID: {study['study_uid']}")
            response = requests.post(
                FHIR_SERVER,
                json=bundle,
                headers={"Content-Type": "application/fhir+json"}
            )
            if response.status_code in [200, 201]:
                print("✅ ImagingStudy uploaded successfully.")
            else:
                print(f"❌ Failed to upload ImagingStudy. {response.status_code}: {response.text}")
        except Exception as e:
            print(f"❌ Error on attempt {attempt+1}: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"🔁 Retrying in {RETRY_DELAY_SEC} seconds...")
                time.sleep(RETRY_DELAY_SEC)
            else:
                print("🚨 Max retries reached. Sending message to dead-letter queue.")
                dlq_producer.send("imaging.failed", study)
                dlq_producer.flush()