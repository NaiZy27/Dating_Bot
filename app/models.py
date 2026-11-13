from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional
from datetime import datetime, time, timedelta, timezone
from redis.asyncio import Redis
from enum import StrEnum
import html

# Лимит лайков сбрасывается в полночь по Москве, а не по часам сервера (в Docker там UTC)
MSK = timezone(timedelta(hours=3))
# Лимиты лайков (письмо — тоже лайк); в час — только без премиума
DAILY_LIKES_LIMIT = 30
PREMIUM_DAILY_LIKES_LIMIT = 100
HOURLY_LIKES_LIMIT = 10


class Gender(StrEnum):
    MALE = "Мужчина"
    FEMALE = "Женщина"


class Profile(BaseModel):
    id: Optional[int] = Field(None, frozen=True)
    username: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    city: Optional[str] = None
    text: Optional[str] = None
    media: list[str] = Field(default_factory=list)
    
    active: bool = False
    premium: bool = False

    gender: Optional[Gender] = None
    target_gender: Optional[Gender] = None

    # --- ПРОПЕРТИ ---

    @property
    def max_likes_limit(self) -> int:
        return PREMIUM_DAILY_LIKES_LIMIT if self.premium else DAILY_LIKES_LIMIT

    @property
    def link(self) -> str:
        return f"https://t.me/{self.username}" if self.username else f"tg://user?id={self.id}"

    # -- Готовый текст для профиля; linked — имя становится ссылкой на Telegram (для премиума) --
    def preview_text(self, linked: bool = False) -> str:
        name = html.escape(self.name or "Без имени")
        if linked:
            name = f'<a href="{self.link}">{name}</a>'
        city = html.escape(self.city or "Город не указан")
        header = f"<b>{name}, {self.age}</b>, {city}"
    
        if self.text:
            return f"{header}\n\n{html.escape(self.text)}"
        return header
    

    # --- ВАЛИДАТОРЫ ---

    @field_validator("gender", "target_gender", mode="before")
    @classmethod
    def normalize_gender(cls, value: str) -> str:
        # Кнопка «Кого ищу» во множественном числе, а храним в единственном
        return {"Мужчины": "Мужчина", "Женщины": "Женщина"}.get(value, value)
    

    @field_validator("age")
    @classmethod
    def check_age(cls, value: int) -> int:
        if value is not None and value < 18:
            raise ValueError("🔞 Возраст строго 18+")
        if value is not None and value > 99:
            raise ValueError("⚠️ Укажи настоящий возраст")
        return value

    @field_validator("name")
    @classmethod
    def check_name(cls, value: str) -> str:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("❌ Имя не может быть пустым")
            if len(value) > 15:
                raise ValueError("⚠️ Имя не может быть длиннее 15 символов")
        return value

    @field_validator("city")
    @classmethod
    def format_city(cls, value: str) -> str:
        if value is not None:
            value = value.strip().title()
            if not value:
                raise ValueError("❌ Город не может быть пустым")
            if len(value) > 50:
                raise ValueError("⚠️ Название города не может быть длиннее 50 символов")
        return value
    
    @field_validator("text")
    @classmethod
    def check_text(cls, value: str) -> str:
        if value:
            if len(value) > 400:
                raise ValueError("⚠️ Описание не может быть длиннее 400 символов")
        return value
    
    @field_validator("media")
    @classmethod
    def check_media(cls, value: list) -> list:
        if not value:
            raise ValueError("📸 Нужно загрузить хотя бы одно фото")
        return value
    
    @staticmethod
    def format_error(e: ValidationError) -> str:
        try:
            raw_msg = e.errors()[0]['msg']
            return raw_msg.replace("Value error, ", "")
        except (IndexError, KeyError):
            return "⚠️ Произошла ошибка валидации данных."


    # --- МЕТОДЫ ---

    # -- Проверка лимитов (Redis) --
    async def use_like(self, redis: Redis) -> Optional[str]:
        """Тратит один лайк. None — можно, иначе текст, почему нельзя."""
        # Часовой лимит проверяем первым: отказ по нему не должен тратить дневные лайки
        if not self.premium:
            hour_key = f"likes_hour:{self.id}"
            if await incr_with_ttl(redis, hour_key, 3600) > HOURLY_LIKES_LIMIT:
                minutes = await redis.ttl(hour_key) // 60 + 1
                return f"Не больше {HOURLY_LIKES_LIMIT} лайков в час. Попробуй через {minutes} мин ⏳\nС премиумом ⭐ лимита в час нет"

        now = datetime.now(MSK)
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=MSK)
        if await incr_with_ttl(redis, f"likes:{self.id}", int((tomorrow - now).total_seconds())) > self.max_likes_limit:
            return f"На сегодня лайки закончились ({self.max_likes_limit} в день). Возвращайся завтра 🌙"
        return None


async def incr_with_ttl(redis: Redis, key: str, ttl: int) -> int:
    """Счётчик, который сам исчезнет через ttl секунд от первого увеличения."""
    # MULTI/EXEC: INCR и EXPIRE выполняются вместе, поэтому ключ не останется без срока жизни;
    # nx — срок ставится только новому ключу, повторные INCR его не продлевают
    async with redis.pipeline(transaction=True) as pipe:
        count, _ = await pipe.incr(key).expire(key, ttl, nx=True).execute()
    return count
    
