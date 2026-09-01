import json

import boto3

from app.core.config import settings


class SQSQueue:
    def __init__(self):
        self.client = boto3.client(
            "sqs",
            region_name=settings.aws_region,
        )

    def send_message(self, message: dict):
        response = self.client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(message),
        )

        return response["MessageId"]


sqs_queue = SQSQueue()