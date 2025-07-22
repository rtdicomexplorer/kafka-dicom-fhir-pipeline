# consumer_fhir_uploader.py
from kafka import KafkaConsumer
import json
import requests

FHIR_SERVER = "http://localhost:8080/fhir"  # Use your FHIR server

consumer = KafkaConsumer(
    "imaging.metadata",
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',  # <-- Important
    enable_auto_commit=True,
    group_id="fhir-uploader-group",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Consumer uploaded: started")
print("👂 Waiting for messages on topic 'imaging.metadata'...")

for msg in consumer:
    metadata = msg.value
    print(f"📥 Step 8: Received metadata from 'imaging.metadata': {metadata}")

    patient_id = metadata["patient_id"]
    modality_code = metadata["modality"]
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "fullUrl": f"urn:uuid:patient-{patient_id}",
                "resource": {
                    "resourceType": "Patient",
                    "id": patient_id,
                    "identifier": [{
                        "system": "http://hospital.smartcare.org/patients",
                        "value": patient_id
                    }],
                    "name": [{
                        "use": "official",
                        "family": "Test",
                        "given": ["Patient"]
                    }]
                },
                "request": {
                    "method": "PUT",
                    "url": f"Patient/{patient_id}"
                }
            },
            {
                "resource": {
                    "resourceType": "ImagingStudy",
                    "subject": {
                        "reference": f"Patient/{patient_id}"
                    },
                    "modality": [
                        {
                            "system": "http://dicom.nema.org/resources/ontology/DCM",
                            "code": modality_code
                        }
                    ],
                    "started": metadata["scan_time"]
                },
                "request": {
                    "method": "POST",
                    "url": "ImagingStudy"
                }
            }
        ]
    }


    # imaging_study = {
    #     "resourceType": "ImagingStudy",
    #     "subject": {
    #         "reference": f"Patient/{metadata['patient_id']}"
    #     },
    #     "modality": [
    #         {
    #             "system": "http://dicom.nema.org/resources/ontology/DCM",
    #             "code": metadata["modality"]
    #         }
    #     ],
    #     "started": metadata["scan_time"]
    # }
    print("📦 Step 9: Sending Bundle (Patient + ImagingStudy) to FHIR server...")
    response = requests.post(f"{FHIR_SERVER}", json=bundle)
     
    if response.status_code == 201:
        print(f"✅ Step 10: ImagingStudy created successfully for Patient {metadata['patient_id']}")
    else:
        print(f"❌ Step 10: Failed to create ImagingStudy. Status: {response.status_code}, Body: {response.text}")