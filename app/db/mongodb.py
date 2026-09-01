from pymongo import MongoClient
from app.core.config import settings


client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=5000,
)

db = client[settings.mongodb_database]


def get_database():
    return db


def check_connection():
    client.admin.command("ping")