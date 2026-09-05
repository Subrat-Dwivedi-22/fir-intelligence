from app.db.mongodb import db


class ActivityRepository:

    def create(self, activity: dict) -> dict:
        db.case_activity.insert_one(activity)

        activity.pop("_id", None)

        return activity

    def get_by_case(self, case_id: str) -> list[dict]:
        return list(
            db.case_activity.find(
                {"case_id": case_id},
                {"_id": 0},
            ).sort(
                "timestamp",
                -1,
            )
        )
