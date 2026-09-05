import json
import logging
import signal

import boto3

from app.core.config import settings
from worker.processor import start_fir_processing


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


sqs = boto3.client(
    "sqs",
    region_name=settings.aws_region,
)


running = True


def shutdown_handler(signum, frame):
    global running

    logger.info(
        "Received shutdown signal %s. "
        "Stopping worker after current message.",
        signum,
    )

    running = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


def main():
    logger.info("FIR worker started")
    logger.info("Queue: %s", settings.sqs_queue_url)

    while running:

        response = sqs.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=960,
        )

        messages = response.get("Messages", [])

        if not messages:
            continue

        for message in messages:

            if not running:
                break

            try:
                body = json.loads(message["Body"])

                logger.info(
                    "Processing job=%s case=%s document=%s",
                    body.get("job_id"),
                    body.get("case_id"),
                    body.get("document_id"),
                )

                start_fir_processing(body)

                sqs.delete_message(
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )

                logger.info(
                    "Message processed successfully."
                )

            except Exception:
                logger.exception(
                    "Processing failed. "
                    "Message will remain in SQS for retry."
                )

    logger.info("FIR worker stopped.")


if __name__ == "__main__":
    main()