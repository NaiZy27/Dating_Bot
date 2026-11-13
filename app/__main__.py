import asyncio
import logging

from app import db
from app.handlers import routers
from app.loader import bot, dp


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db()
    dp.include_routers(*routers)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
