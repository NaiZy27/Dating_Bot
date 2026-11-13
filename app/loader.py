from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.config import config

bot = Bot(token=config.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML"))
redis = Redis.from_url(str(config.redis_url))
dp = Dispatcher(storage=RedisStorage(redis))
