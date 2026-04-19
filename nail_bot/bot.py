import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TOKEN
from database import (
    init_db,
    get_upcoming_for_reminder, mark_reminded,
    get_all_appointments_for_review_bot, mark_review_asked,
)
from handlers import user, admin
from keyboards import rating_kb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════════
#  Напоминание за 24 часа до визита
# ════════════════════════════════════════════

async def reminder_loop(bot: Bot):
    while True:
        try:
            for apt in await get_upcoming_for_reminder():
                dt        = apt['datetime'].replace('T', ' ')[:16]
                time_only = dt.split(' ')[1] if ' ' in dt else dt
                try:
                    await bot.send_message(
                        apt['user_id'],
                        f"⏰ *Напоминание о записи!*\n\n"
                        f"Привет, *{apt['user_name']}*!\n\n"
                        f"Завтра в *{time_only}* у вас:\n"
                        f"💅 *{apt['name']}*\n\n"
                        f"Ждём вас! 💕",
                        parse_mode="Markdown"
                    )
                    await mark_reminded(apt['id'])
                    log.info(f"Reminder → user {apt['user_id']} apt {apt['id']}")
                except Exception as e:
                    log.warning(f"Reminder failed user {apt['user_id']}: {e}")
        except Exception as e:
            log.error(f"reminder_loop error: {e}")
        await asyncio.sleep(30 * 60)  # каждые 30 минут


# ════════════════════════════════════════════
#  Автозапрос отзыва после визита
# ════════════════════════════════════════════

async def review_loop(bot: Bot):
    while True:
        await asyncio.sleep(60 * 60)  # каждый час
        try:
            for apt in await get_all_appointments_for_review_bot():
                try:
                    await bot.send_message(
                        apt['user_id'],
                        f"💬 *{apt['user_name']}*, как прошёл визит?\n\n"
                        f"Оцените работу мастера — это займёт 10 секунд 🙏",
                        parse_mode="Markdown",
                        reply_markup=rating_kb(apt['id'])
                    )
                    await mark_review_asked(apt['id'])
                    log.info(f"Review request → user {apt['user_id']} apt {apt['id']}")
                except Exception as e:
                    log.warning(f"Review request failed user {apt['user_id']}: {e}")
        except Exception as e:
            log.error(f"review_loop error: {e}")


# ════════════════════════════════════════════
#  ЗАПУСК
# ════════════════════════════════════════════

async def main():
    await init_db()

    bot = Bot(token=TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())

    dp.include_router(user.router)
    dp.include_router(admin.router)

    asyncio.create_task(reminder_loop(bot))
    asyncio.create_task(review_loop(bot))

    log.info("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())