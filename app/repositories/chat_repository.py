from app.db.mongodb import db
from app.models.chat import create_chat_message


class ChatRepository:

    def create(
        self,
        case_id: str,
        role: str,
        content: str,
    ) -> dict:

        message = create_chat_message(
            case_id=case_id,
            role=role,
            content=content,
        )

        db.case_chat_messages.insert_one(
            message
        )

        return message

    def get_history(
        self,
        case_id: str,
    ) -> list[dict]:

        return list(
            db.case_chat_messages.find(
                {
                    "case_id": case_id,
                },
                {
                    "_id": 0,
                },
            ).sort(
                "created_at",
                1,
            )
        )
