from sqlalchemy.orm import Session
from app.models.preference import UserPreference
from app.schemas.user import UserPreferenceUpdate


class PreferenceRepository:
    """Repository for UserPreference operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: str) -> UserPreference:
        pref = self.db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            pref = UserPreference(user_id=user_id)
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def update_preferences(self, user_id: str, data: UserPreferenceUpdate) -> UserPreference:
        pref = self.get_by_user_id(user_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(pref, field, value)
        self.db.commit()
        self.db.refresh(pref)
        return pref

