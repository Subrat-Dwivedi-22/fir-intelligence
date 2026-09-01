from app.db.mongodb import db


class CaseRepository:

    def get_by_id(
        self,
        case_id: str,
    ) -> dict | None:

        return db.cases.find_one(
            {
                "case_id": case_id,
            },
            {
                "_id": 0,
            },
        )

    def get_all(self) -> list[dict]:

        return list(
            db.cases.find(
                {},
                {
                    "_id": 0,
                },
            ).sort(
                "created_at",
                -1,
            )
        )
