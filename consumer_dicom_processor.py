# consumer_dicom_processor.py
from kafka import KafkaConsumer, KafkaProducer
import json
import pydicom

consumer = KafkaConsumer(
    "imaging.raw",
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
print("consumer_processor: started'")
for msg in consumer:
    event = msg.value
    dicom_path = event["dicom_file_path"]
    print(f"📥 Step 4: Received message from 'imaging.raw': {event}")
    print(f"🔍 Step 5: Loading DICOM file: {dicom_path}")
    
    # Simulate DICOM parsing (replace with actual file path)
    ds = pydicom.dcmread(dicom_path)
    
    metadata = {
        "patient_id": event["patient_id"],
        "modality": ds.Modality,
        "body_part_examined": getattr(ds, "BodyPartExamined", "Unknown"),
        "scan_time": event["timestamp"]
    }
    print(f"📄 Step 6: Extracted metadata: {metadata}")
    producer.send("imaging.metadata", metadata)
    producer.flush()
    print("📤 Step 7: Sent metadata to Kafka topic 'imaging.metadata'")
