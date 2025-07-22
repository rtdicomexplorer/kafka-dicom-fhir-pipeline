## 🧱 Architecture Overview

- [DICOM Modality Client] 
     - │ (C-STORE)
     - ▼
- [DICOM Receiver (SCP)]
     - │
     - ▼                            Kafka Topics
 - Push event to →──────[Topic: imaging.raw]─────▶ [DICOM Metadata Processor]
                                                    - │
                                                    - ▼
                                          - [Topic: imaging.metadata]
                                                    - │
                                                    - ▼
                                       - [FHIR Uploader → FHIR Server]





### 📂 Project File Structure
medical_kafka_pipeline/
│
├── dicom_client.py                # Simulates modality (MRI)
├── dicom_receiver.py              # DICOM SCP + Kafka producer
├── consumer_dicom_processor.py    # Kafka consumer → extract DICOM metadata
├── consumer_fhir_uploader.py      # Kafka consumer → FHIR POST
├── docker-compose.yml             # Kafka + Zookeeper
├── received_dicoms/               # Folder for received DICOM files
└── mri_sample.dcm                 # Sample DICOM file



### 🧠 Summary of Steps (Bullet Format)
✅ docker-compose up -d (Kafka and Zookeeper)

✅ python dicom_receiver.py (Receiver + Kafka producer)

✅ python consumer_dicom_processor.py (Kafka → metadata)

✅ python consumer_fhir_uploader.py (Kafka → FHIR server)

✅ python dicom_client.py (Send DICOM to receiver)