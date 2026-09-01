import json

from worker.processor import start_fir_processing


def handler(event, context):
    for record in event.get("Records", []):
        body = json.loads(record["body"])

        start_fir_processing(body)

    return {
        "statusCode": 200,
        "processed": len(event.get("Records", [])),
    }