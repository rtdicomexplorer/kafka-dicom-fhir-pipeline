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





### Send more studies present in study-folder
   +------------------+       +-------------------+       +--------------------------+
   |  DICOM Sender    | ----> |  DICOM Receiver    | ----> | Kafka Topic: imaging.raw |
   | (study-by-study) |       | (save + publish)  |       +--------------------------+
   +------------------+       +-------------------+                 |
                                                                  ⬇
                                                  +-----------------------------+
                                                  | Kafka Consumer: Study Grouper|
                                                  | - Groups by StudyInstanceUID |
                                                  | - Sends to imaging.study.ready|
                                                  +-----------------------------+
                                                                  ⬇
                                         +------------------------------------+
                                         | Kafka Consumer: FHIR Uploader     |
                                         | - Creates ImagingStudy Bundle     |
                                         | - Sends to FHIR Server via REST   |
                                         +------------------------------------+

### Message flow summary

| Step | Source                                | Target              | Kafka Topic           | Description                              |
| ---- | ------------------------------------- | ------------------- | --------------------- | ---------------------------------------- |
| 1    | `dicom_sender.py`                     | `dicom_receiver.py` | —                     | Sends DICOM via C-STORE                  |
| 2    | `dicom_receiver.py`                   | Kafka Broker        | `imaging.raw`         | Emits metadata message per DICOM file    |
| 3    | `consumer_grouped_study_processor.py` | Kafka Broker        | `imaging.study.ready` | Groups by study and emits study-level    |
| 4    | `consumer_fhir_uploader.py`           | FHIR Server         | —                     | Creates + sends FHIR ImagingStudy bundle |



### 📂 Project File Structure
project-root/
├── study_folder/                  # Input DICOM files (can include subfolders)
├── received_dicoms/              # Where received files are stored
├── bundles/                      # Where FHIR bundles are saved
├── dicom_sender.py               # Send individual DICOM file
├── batch_send_by_study.py       # Scan and send study-by-study
├── dicom_receiver.py            # DICOM C-STORE SCP + Kafka producer
├── consumer_grouped_study_processor.py  # Kafka consumer to group studies
├── consumer_fhir_uploader.py    # Kafka consumer to send ImagingStudy to FHIR



### 🧠 Summary of Steps (Bullet Format)
✅ docker-compose up -d (Kafka and Zookeeper)

✅ python dicom_receiver.py (Receiver + Kafka producer)

✅ python consumer_dicom_processor.py (Kafka → metadata)

✅ python consumer_fhir_uploader.py (Kafka → FHIR server)

✅ python dicom_client.py (Send DICOM to receiver)