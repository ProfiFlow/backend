from datetime import datetime

from pydantic import ValidationError, validate_email
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship, validates

from . import Base


class User(Base):
    __tablename__ = "users"

    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # Профильные данные
    display_name = Column(String(100), nullable=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    avatar_url = Column(String(255), nullable=True)

    # Интеграция с Яндекс OAuth
    yandex_id = Column(Integer, unique=True, nullable=False)
    yandex_token = Column(String(500), nullable=True)
    yandex_token_expires = Column(DateTime, nullable=True)
    yandex_refresh_token = Column(String(500), nullable=True)

    # Интеграция с Яндекс.Трекером
    tracker_associations = relationship("UserTrackerRole", back_populates="user")

    # Технические поля
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)

    # Валидаторы
    @validates("email")
    def validate_email(self, _, email):
        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise ValueError("Invalid email format")
            return email.lower()

    # Методы
    def get_full_name(self) -> str:
        """Возвращает полное имя пользователя"""
        return (
            f"{self.first_name or ''} {self.last_name or ''}".strip()
            or self.display_name
            or ""
        )

    def has_yandex_auth(self) -> bool:
        """Проверяет, привязан ли Яндекс-аккаунт"""
        return self.yandex_id is not None

    def has_tracker_access(self) -> bool:
        """Проверяет доступ к Яндекс.Трекеру"""
        return bool(self.yandex_token)

    def is_token_expired(self) -> bool:
        """Проверяет истек ли срок действия Яндекс-токена"""
        if not self.yandex_token_expires:
            return True
        return datetime.utcnow() > self.yandex_token_expires

    def __repr__(self):
        return f"<User(id={self.id}, yandex_id={self.yandex_id})>"
