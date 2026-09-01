import boto3

client = boto3.client(
    "bedrock-runtime",
    region_name="ap-south-1",
)

response = client.converse(
    modelId="apac.amazon.nova-micro-v1:0",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "text": "Reply with exactly: Bedrock is working."
                }
            ],
        }
    ],
    inferenceConfig={
        "maxTokens": 50,
        "temperature": 0,
    },
)

print(
    response["output"]["message"]["content"][0]["text"]
)