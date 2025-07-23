# kafka_utils.py

import sys
import io
import signal

# Ensure UTF-8 output everywhere (especially on Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def run_consumer_loop(consumer, handler, name="KafkaConsumer"):
    """
    Reusable loop that handles clean shutdown of Kafka consumers.
    
    :param consumer: KafkaConsumer instance
    :param handler: function to call with each message
    :param name: name to display on shutdown
    """
    def handle_exit(sig, frame):
        print(f"\n🛑 [{name}] Received shutdown signal. Exiting gracefully...")
        consumer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print(f"👂 [{name}] Listening for messages on topic(s): {consumer.subscription()}")

    try:
        for msg in consumer:
            handler(msg)
    except KeyboardInterrupt:
        handle_exit(None, None)
