import json

import boto3

from app.core.config import settings
from worker.processor import start_fir_processing



sqs = boto3.client(
    "sqs",
    region_name=settings.aws_region,
)





def main():
    print("FIR worker started")
    print(f"Queue: {settings.sqs_queue_url}")

    while True:
        response = sqs.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=60,
        )

        messages = response.get("Messages", [])

        if not messages:
            continue

        for message in messages:
            try:
                body = json.loads(message["Body"])

                start_fir_processing(body)

                sqs.delete_message(
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )

                print("✓ Message processed")

            except Exception as exc:
                print(f"✗ Processing failed: {exc}")


if __name__ == "__main__":
    main()