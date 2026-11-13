from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, RedisDsn


class Settings(BaseSettings):
    bot_token: SecretStr
    database_url: SecretStr
    redis_url: RedisDsn
    # Telegram ID модератора, которому пересылаются жалобы (необязательно)
    admin_id: Optional[int] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

config = Settings()
