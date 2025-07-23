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


### latest version with retri logic and consumer error messages
🧠 Project Overview: DICOM to FHIR Pipeline with Kafka
This system ingests DICOM files, extracts metadata, groups them into studies, and converts them into FHIR ImagingStudy bundles to send to a FHIR server. It uses Kafka to orchestrate decoupled stages and ensures resilience with retry + dead-letter queue logic.

🔄 Full Workflow
📤 1. dicom_sender.py
Reads .dcm files from a folder.

Sends them via DICOM C-STORE to a receiver (dicom_receiver).

Supports multiple patients, studies, series, subfolders.

📥 2. dicom_receiver.py
Listens for incoming DICOM files (acts as a DICOM SCP).

Saves received files to ./received_dicoms/.

Extracts metadata:

PatientID, StudyInstanceUID, SeriesInstanceUID, SOPInstanceUID

Also PatientName, PatientSex, AccessionNumber

Publishes metadata to Kafka topic: imaging.raw

📦 3. consumer_grouped_study_processor.py
Listens on imaging.raw

Groups incoming files by StudyInstanceUID into study batches using a TTL cache

Once a study is considered "complete" (10 seconds inactivity), emits:

study_uid, patient_id, accession_number, modality, series, instances, and patient info

Sends to Kafka topic: imaging.study.ready

📤 4. consumer_fhir_uploader.py
Listens on imaging.study.ready

Builds a FHIR transaction bundle with:

A Patient resource (from DICOM info: name, sex, accession number)

An ImagingStudy resource (with series + instances)

Sends the bundle to the FHIR server (http://localhost:8080/fhir)

Also saves a local copy under ./bundles/

✅ Now with:

Retry logic: retries failed FHIR sends up to 3 times

DLQ support: failed messages go to imaging.failed

⚠️ 5. consumer_dlq_handler.py
Reads from Kafka topic: imaging.failed

Two versions:

🔧 Manual mode: prompts user to retry, skip, or quit

🔁 Auto-retry mode: re-sends all failed messages back to imaging.study.ready after a delay

### 📊 Kafka Topics
| Kafka Topic           | Purpose                                      |
| --------------------- | -------------------------------------------- |
| `imaging.raw`         | Raw metadata from each received DICOM file   |
| `imaging.study.ready` | Grouped study-level metadata for FHIR upload |
| `imaging.failed`      | Failed FHIR bundle uploads                   |


### 🛡️ Reliability Features
✅ Retry logic in uploader (3 attempts with delay)

✅ DLQ for unprocessed messages

✅ Manual + auto DLQ replay support

✅ Local FHIR bundle backups

🧪 Easily testable with many patient/study files in folders


### 🧰 Tech Stack
| Component      | Library/Tool                   |
| -------------- | ------------------------------ |
| DICOM I/O      | `pydicom`, `pynetdicom`        |
| Messaging      | `Kafka`, `kafka-python`        |
| Metadata cache | `cachetools.TTLCache`          |
| FHIR Bundle    | JSON, `requests`               |
| Resilience     | Retry logic, DLQ, TTL grouping |

### 📂 Folder Structure Example
project_root/
├── study_folder/              # Input DICOMs for sender
├── received_dicoms/           # Files saved by receiver
├── bundles/                   # Saved FHIR bundles
├── dicom_sender.py
├── dicom_receiver.py
├── consumer_grouped_study_processor.py
├── consumer_fhir_uploader.py
├── consumer_dlq_handler.py
