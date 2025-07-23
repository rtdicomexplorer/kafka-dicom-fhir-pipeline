from kafka import KafkaConsumer
import json
from kafka_utils import run_consumer_loop
from log_utils import setup_logger
log = setup_logger("consumer_dlq_handler", "consumer_dlq_handler.log")
log.info(f"✅  DLQ consumer started")
consumer = KafkaConsumer(
    "imaging.dlq",
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id="dlq-handler-group",
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

def handle_message(msg):
    event = msg.value
    log_txt =  f"📡  DLQ received event: {event}"
    print(log_txt)
    log.info(log_txt)

run_consumer_loop(consumer, handle_message, name="DLQ Handler")
