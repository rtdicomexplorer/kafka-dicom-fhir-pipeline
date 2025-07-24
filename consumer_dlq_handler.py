from kafka import KafkaConsumer
import json
from kafka_utils import run_consumer_loop
from log_utils import setup_logger
from service_names import DLQ_HANDLER
from dotenv import load_dotenv
import os
log = setup_logger(DLQ_HANDLER, f"{DLQ_HANDLER}.log")
log.info(f"✅ {DLQ_HANDLER}  started")
load_dotenv(override=True)

bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
#in docker you need to use kafka instead localhost
consumer = KafkaConsumer(
    "imaging.dlq",
    bootstrap_servers=bootstrap_servers,
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

run_consumer_loop(consumer, handle_message, name=DLQ_HANDLER)
