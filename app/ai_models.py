"""AI 模型配置的 CRUD 操作"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import AIModel

logger = logging.getLogger(__name__)


class AIModelManager:
    def create(self, db: Session, *, name: str, provider: str, api_base: str,
               api_key: str, model_name: str) -> AIModel:
        model = AIModel(
            name=name, provider=provider, api_base=api_base.rstrip("/"),
            api_key=api_key, model_name=model_name
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    def get(self, db: Session, id: int) -> Optional[AIModel]:
        return db.query(AIModel).filter(AIModel.id == id).first()

    def list_all(self, db: Session) -> List[AIModel]:
        return db.query(AIModel).order_by(AIModel.created_at.desc()).all()

    def get_active(self, db: Session) -> Optional[AIModel]:
        return db.query(AIModel).filter(AIModel.is_active == 1).first()

    def set_active(self, db: Session, id: int) -> Optional[AIModel]:
        db.query(AIModel).filter(AIModel.is_active == 1).update({"is_active": 0})
        model = self.get(db, id)
        if model:
            model.is_active = 1
            db.commit()
            db.refresh(model)
        return model

    def update(self, db: Session, id: int, **kwargs) -> Optional[AIModel]:
        model = self.get(db, id)
        if not model:
            return None
        for key, value in kwargs.items():
            if value is not None:
                if key == "api_base":
                    value = value.rstrip("/")
                setattr(model, key, value)
        db.commit()
        db.refresh(model)
        return model

    def delete(self, db: Session, id: int) -> bool:
        model = self.get(db, id)
        if model:
            db.delete(model)
            db.commit()
            return True
        return False


ai_model_manager = AIModelManager()
