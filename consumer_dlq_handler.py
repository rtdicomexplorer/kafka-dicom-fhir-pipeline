from kafka import KafkaConsumer, KafkaProducer
import json
import os
import time

# Topics
DLQ_TOPIC = "imaging.failed"
RETRY_TOPIC = "imaging.study.ready"  # original topic

# Kafka setup
consumer = KafkaConsumer(
    DLQ_TOPIC,
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="dlq-handler-group",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda m: json.dumps(m).encode('utf-8')
)

print(f"🛠️ DLQ handler started. Listening on '{DLQ_TOPIC}'...")
print("🔁 Press Ctrl+C to stop.")

try:
    for msg in consumer:
        failed_study = msg.value

        print("\n❗ Failed Study Received from DLQ:")
        print(json.dumps(failed_study, indent=2))

        user_input = input("\n➡️ Retry this message? (y = yes, s = skip, q = quit): ").strip().lower()
        if user_input == "y":
            producer.send(RETRY_TOPIC, failed_study)
            producer.flush()
            print("✅ Message re-sent to 'imaging.study.ready'.")
        elif user_input == "q":
            print("👋 Exiting DLQ handler.")
            break
        else:
            print("⏭️ Skipping this message.")

except KeyboardInterrupt:
    print("\n🛑 Stopped by user.")
