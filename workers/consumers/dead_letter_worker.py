from common.kafka import DEADLETTER_TOPIC, json_consumer
from common.logging import configure_logging

logger = configure_logging("worker-dead-letter")


def main() -> None:
    consumer = json_consumer("crypto-signal-radar-dead-letter", [DEADLETTER_TOPIC])
    logger.info("watching %s", DEADLETTER_TOPIC)
    while True:
        records = consumer.poll(timeout_ms=5000)
        for messages in records.values():
            for message in messages:
                logger.warning("dead letter observed: %s", message.value)


if __name__ == "__main__":
    main()
