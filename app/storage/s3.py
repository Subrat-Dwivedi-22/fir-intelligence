import boto3

from app.core.config import settings


class S3Storage:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            region_name=settings.aws_region,
        )

    def upload_file(
        self,
        file_path: str,
        key: str,
        content_type: str = "application/pdf",
    ):
        self.client.upload_file(
            file_path,
            settings.s3_bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
            },
        )

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/pdf",
    ):
        self.client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def download_file(
        self,
        key: str,
        file_path: str,
    ):
        self.client.download_file(
            settings.s3_bucket,
            key,
            file_path,
        )

    def delete_file(self, key: str):
        self.client.delete_object(
            Bucket=settings.s3_bucket,
            Key=key,
        )


s3_storage = S3Storage()