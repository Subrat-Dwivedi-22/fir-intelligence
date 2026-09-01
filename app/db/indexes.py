from app.db.mongodb import db


def create_indexes():
    db.cases.create_index(
        "case_id",
        unique=True,
    )

    db.documents.create_index(
        "document_id",
        unique=True,
    )

    db.documents.create_index(
        "case_id",
    )

    db.documents.create_index(
        "source.sha256",
    )

    db.persons.create_index(
        "person_id",
        unique=True,
    )

    db.persons.create_index(
        "identity.name",
    )

    db.persons.create_index(
        "contact.phones",
    )

    db.case_persons.create_index(
        [
            ("case_id", 1),
            ("person_id", 1),
        ],
        unique=True,
    )

    db.case_persons.create_index(
        "person_id",
    )

    db.incidents.create_index(
        "incident_id",
        unique=True,
    )

    db.incidents.create_index(
        "case_id",
    )

    db.entities.create_index(
        "entity_id",
        unique=True,
    )

    db.entities.create_index(
        [
            ("type", 1),
            ("normalized_value", 1),
        ],
    )

    db.relationships.create_index(
        "relationship_id",
        unique=True,
    )

    db.relationships.create_index(
        [
            ("from.type", 1),
            ("from.id", 1),
        ],
    )

    db.relationships.create_index(
        [
            ("to.type", 1),
            ("to.id", 1),
        ],
    )

    db.ingestion_jobs.create_index(
        "job_id",
        unique=True,
    )

    db.ingestion_jobs.create_index(
        "case_id",
    )

    db.document_pages.create_index(
        [
            ("document_id", 1),
            ("page_number", 1),
        ],
        unique=True,
    )

    db.document_pages.create_index(
        "document_id",
    )

    db.case_chat_messages.create_index(
        [
            ("case_id", 1),
            ("created_at", 1),
        ],
    )