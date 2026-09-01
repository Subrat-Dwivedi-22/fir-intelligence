from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FIR Intelligence Ingestion API"
    environment: str = "development"

    mongodb_uri: str = "mongodb://admin:change-me@localhost:27017/?authSource=admin"
    mongodb_database: str = "criminal_intelligence"

    aws_region: str = "ap-south-1"

    s3_bucket: str = "fir-intelligence-documents"
    sqs_queue_url: str = ""

    person_id_hmac_secret: str
    gemini_api_key: str

    max_fir_size_mb: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()