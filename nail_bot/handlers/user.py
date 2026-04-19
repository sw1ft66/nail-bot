"""
user.py — пользовательская часть бота.

Исправленные баги:
  1. Портфолио: после delete() используем message.answer (чат), а не
     callback.message.answer_photo (старый объект). Кнопка «◀️ Меню»
     триггерится через pf_back и шлёт новое сообщение с меню.
  2. Контакты: если предыдущее сообщение было фото — edit_text падает.
     Теперь всегда пробуем edit, при ошибке — delete + answer.
  3. Отзывы: state устанавливается ДО ответа бота, порядок правильный.
     skip_review_text обрабатывается без StateFilter (он глобальный).
  4. Таймаут 20 сек: после ввода имени / контакта запускается asyncio.sleep,
     если пользователь не ответил — сбрасываем FSM и шлём напоминание.
"""

import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from config import (
    ADMINS, MASTER_NAME, MASTER_TG, MASTER_PHONE,
    MASTER_CITY, SUPPORT_USERNAME, WELCOME_TEXT, IDLE_TIMEOUT,
)
from database import (
    get_services, get_free_slots, create_appointment,
    get_user_appointments, get_slot_by_id, get_service_by_id,
    cancel_appointment, get_last_user_service,
    get_portfolio,
    get_reviews, get_average_rating, add_review,
    get_appointments_for_review,
)
from keyboards import (
    main_menu, prices_kb, contacts_kb, reviews_kb, back_main_kb,
    services_keyboard, slots_keyboard, contact_keyboard,
    confirm_kb, my_appointments_kb,
    portfolio_nav_kb, portfolio_empty_kb,
    rating_kb, skip_text_kb,
)
from states import BookingStates, ReviewStates

router = Router()

STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


# ──────────────────────────────────────────
#  Вспомогательная функция: безопасное редактирование
#  (если сообщение было с фото — edit_text упадёт, тогда удаляем + новое)
# ──────────────────────────────────────────

async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None, **kwargs):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, **kwargs)


# ──────────────────────────────────────────
#  Таймер бездействия
# ──────────────────────────────────────────

async def idle_timer(bot: Bot, chat_id: int, user_id: int, state: FSMContext):
    """Ждёт IDLE_TIMEOUT секунд. Если пользователь всё ещё в FSM — сбрасывает."""
    await asyncio.sleep(IDLE_TIMEOUT)
    current = await state.get_state()
    if current is not None:
        await state.clear()
        is_admin = user_id in ADMINS
        try:
            await bot.send_message(
                chat_id,
                "⏱ *Сессия завершена* из-за бездействия.\n\nВозвращаю вас в главное меню:",
                parse_mode="Markdown",
                reply_markup=main_menu(is_admin)
            )
        except Exception:
            pass


# ════════════════════════════════════════════════════════
#  СТАРТ
# ════════════════════════════════════════════════════════

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id in ADMINS
    greeting = WELCOME_TEXT.format(master_name=MASTER_NAME)
    await message.answer(
        f"✨ {greeting}",
        parse_mode="Markdown",
        reply_markup=main_menu(is_admin)
    )
    # Проверяем не остался ли отзыв после визита
    pending = await get_appointments_for_review(message.from_user.id)
    if pending:
        apt = pending[0]
        await message.answer(
            f"💬 Вы были у нас на *{apt['name']}*!\n\n"
            f"Оцените работу мастера — это очень важно 🙏",
            parse_mode="Markdown",
            reply_markup=rating_kb(apt['id'])
        )


# ════════════════════════════════════════════════════════
#  УНИВЕРСАЛЬНАЯ НАВИГАЦИЯ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data.in_(["back", "back_to_main", "menu"]))
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    is_admin = callback.from_user.id in ADMINS
    await safe_edit(
        callback,
        "🏠 *Главное меню*\n\nЧем могу помочь?",
        reply_markup=main_menu(is_admin),
        parse_mode="Markdown"
    )
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ЦЕНЫ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "prices")
async def show_prices(callback: CallbackQuery):
    services = await get_services()
    if not services:
        await callback.answer("Услуги временно не добавлены", show_alert=True)
        return
    lines = ["💅 *Прайс-лист*\n", "━━━━━━━━━━━━━━━━━"]
    for s in services:
        price_fmt = f"{s['price']:,}".replace(",", " ")
        lines.append(f"• *{s['name']}*  —  {price_fmt} ₽")
        if s.get('description'):
            lines.append(f"  _{s['description']}_")
    lines += ["━━━━━━━━━━━━━━━━━",
              "_По вопросам — раздел «Контакты»._"]
    await safe_edit(
        callback,
        "\n".join(lines),
        reply_markup=prices_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ════════════════════════════════════════════════════════
#  КОНТАКТЫ  ← ИСПРАВЛЕНО: safe_edit + правильная клавиатура
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "contacts")
async def show_contacts(callback: CallbackQuery):
    phone_line = f"📱 Телефон: {MASTER_PHONE}\n" if MASTER_PHONE else ""

    text = (
        f"📞 Контакты\n\n"
        f"💅 Мастер: {MASTER_NAME}\n"
        f"✈️ Telegram: {MASTER_TG}\n"
        f"{phone_line}\n"
        f"🛠 Поддержка: {SUPPORT_USERNAME}"
    )

    await callback.message.answer(
        text,
        reply_markup=contacts_kb()
    )

    await callback.answer()


# ════════════════════════════════════════════════════════
#  ПОРТФОЛИО  ← ИСПРАВЛЕНО: не используем callback.message после delete()
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "portfolio")
async def show_portfolio(callback: CallbackQuery):
    await _send_portfolio_page(callback, 0)

@router.callback_query(F.data.startswith("pf_"))
async def portfolio_nav(callback: CallbackQuery):
    data = callback.data  # "pf_0", "pf_3", "pf_back"
    if data == "pf_back":
        # Кнопка «◀️ Меню» — удаляем фото, шлём главное меню новым сообщением
        is_admin = callback.from_user.id in ADMINS
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🏠 *Главное меню*\n\nЧем могу помочь?",
            parse_mode="Markdown",
            reply_markup=main_menu(is_admin)
        )
        await callback.answer()
        return
    idx = int(data.split("_")[1])
    await _send_portfolio_page(callback, idx)

async def _send_portfolio_page(callback: CallbackQuery, idx: int):
    photos = await get_portfolio()
    if not photos:
        await safe_edit(
            callback,
            "🖼 *Портфолио*\n\nФото работ пока не добавлены. Загляните позже! 💅",
            reply_markup=portfolio_empty_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    idx   = max(0, min(idx, len(photos) - 1))
    photo = photos[idx]
    desc  = photo.get('description') or f"Работа {idx + 1}"
    cap   = f"🖼 *Портфолио*  ({idx + 1} / {len(photos)})\n\n_{desc}_"

    # Удаляем старое сообщение (может быть текстовым или фото)
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Отправляем новое фото в тот же чат
    await callback.bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=photo['file_id'],
        caption=cap,
        parse_mode="Markdown",
        reply_markup=portfolio_nav_kb(idx, len(photos))
    )
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ОТЗЫВЫ (публичный просмотр)
# ════════════════════════════════════════════════════════

def _reviews_full_kb() -> InlineKeyboardMarkup:
    """Клавиатура раздела отзывов — всегда с кнопкой оставить отзыв."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="leave_review")],
        [InlineKeyboardButton(text="◀️ Главное меню",   callback_data="back_to_main")],
    ])


@router.callback_query(F.data == "reviews")
async def show_reviews(callback: CallbackQuery):
    reviews = await get_reviews(limit=10)
    avg     = await get_average_rating()

    if not reviews:
        await safe_edit(
            callback,
            "⭐ *Отзывы*\n\nОтзывов пока нет. Вы можете стать первым! 😊",
            reply_markup=_reviews_full_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    lines = [
        "⭐ *Отзывы клиентов*\n",
        f"Средняя оценка: *{avg}* / 5.0\n",
        "━━━━━━━━━━━━━━━━━",
    ]
    for r in reviews:
        stars = STARS.get(r['rating'], "⭐")
        lines.append(f"\n{stars} *{r['user_name']}*")
        if r.get('text', '').strip():
            lines.append(f"_{r['text'].strip()}_")

    await safe_edit(
        callback,
        "\n".join(lines),
        reply_markup=_reviews_full_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ── «Оставить отзыв» — пользователь нажимает сам из раздела отзывов ──
@router.callback_query(F.data == "leave_review")
async def leave_review_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(review_apt_id=0, review_rating=0)
    await safe_edit(
        callback,
        "⭐ *Оставить отзыв*\n\n"
        "Выберите оценку — нажмите нужное количество звёзд:",
        reply_markup=rating_kb(0),
        parse_mode="Markdown"
    )
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ОТЗЫВ — оставить  ← ИСПРАВЛЕНО: правильный порядок state + ответа
# ════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    # rate_{apt_id}_{rating}
    parts  = callback.data.split("_")
    apt_id = int(parts[1])
    rating = int(parts[2])

    # Сначала сохраняем state
    await state.update_data(review_apt_id=apt_id, review_rating=rating)
    await state.set_state(ReviewStates.waiting_for_text)

    stars = STARS.get(rating, "⭐")
    await safe_edit(
        callback,
        f"Вы поставили: *{stars}*\n\n"
        f"Напишите пару слов о визите\n"
        f"(или нажмите «Пропустить»):",
        reply_markup=skip_text_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "skip_review")
async def skip_review(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    is_admin = callback.from_user.id in ADMINS
    await safe_edit(
        callback,
        "Спасибо! Ждём вас снова 💕\n\n🏠 *Главное меню*",
        reply_markup=main_menu(is_admin),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "skip_review_text")
async def skip_review_text(callback: CallbackQuery, state: FSMContext):
    """Обрабатываем без StateFilter — работает даже если state сбился."""
    data   = await state.get_data()
    apt_id = data.get('review_apt_id')   # может быть 0 — это нормально
    rating = data.get('review_rating', 5)
    if apt_id is not None and rating:
        await add_review(
            callback.from_user.id,
            callback.from_user.full_name,
            apt_id, rating, ""
        )
    await state.clear()
    is_admin = callback.from_user.id in ADMINS
    await safe_edit(
        callback,
        "✅ *Спасибо за оценку!*\n\nЭто помогает нам становиться лучше 💕",
        reply_markup=main_menu(is_admin),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(ReviewStates.waiting_for_text)
async def review_text(message: Message, state: FSMContext):
    try:
        data   = await state.get_data()
        apt_id = data.get('review_apt_id')   # 0 — ручной отзыв, это ок
        rating = data.get('review_rating', 5)

        await add_review(
            message.from_user.id,
            message.from_user.full_name,
            apt_id,
            rating,
            message.text.strip()
        )
        await state.clear()
        await message.answer(
            "✅ *Спасибо за отзыв!*\n\nМы постоянно совершенствуемся благодаря вам 💕",
            parse_mode="Markdown",
            reply_markup=main_menu(message.from_user.id in ADMINS)
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"review_text error: {e}")
        await state.clear()
        await message.answer(
            "❌ Ошибка при сохранении отзыва. Попробуйте ещё раз.",
            reply_markup=main_menu(message.from_user.id in ADMINS)
        )


# ════════════════════════════════════════════════════════
#  МОИ ЗАПИСИ
# ════════════════════════════════════════════════════════

STATUS_ICON  = {"pending": "🕐", "confirmed": "✅", "cancelled": "❌"}
STATUS_LABEL = {
    "pending":   "ожидает подтверждения",
    "confirmed": "подтверждена ✅",
    "cancelled": "отменена",
}

@router.callback_query(F.data == "my_appointments")
async def show_my_appointments(callback: CallbackQuery):
    appointments = await get_user_appointments(callback.from_user.id)

    if not appointments:
        await safe_edit(
            callback,
            "📋 *Мои записи*\n\nАктивных записей нет. Запишитесь прямо сейчас! 💅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Записаться",   callback_data="book")],
                [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")],
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    lines = ["📋 *Ваши записи:*\n", "━━━━━━━━━━━━━━━━━"]
    for apt in appointments:
        dt    = apt['datetime'].replace('T', ' ')[:16]
        icon  = STATUS_ICON.get(apt['status'], "📋")
        label = STATUS_LABEL.get(apt['status'], apt['status'])
        lines.append(
            f"\n{icon} *{apt['name']}*\n"
            f"     📅 {dt}\n"
            f"     💰 {apt['price']} ₽  •  {label}"
        )

    await safe_edit(
        callback,
        "\n".join(lines),
        reply_markup=my_appointments_kb(appointments),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_apt_"))
async def user_cancel_appointment(callback: CallbackQuery):
    apt_id = int(callback.data.split("_")[2])
    await cancel_appointment(apt_id)
    await callback.answer("✅ Запись отменена", show_alert=True)
    await show_my_appointments(callback)


# ════════════════════════════════════════════════════════
#  БЫСТРАЯ ПЕРЕЗАПИСЬ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "quick_rebook")
async def quick_rebook(callback: CallbackQuery, state: FSMContext):
    last = await get_last_user_service(callback.from_user.id)
    if not last:
        await callback.answer("История записей не найдена", show_alert=True)
        return
    slots = await get_free_slots()
    if not slots:
        await callback.answer("Свободных слотов нет. Загляните позже.", show_alert=True)
        return

    await state.update_data(service_id=last['id'])
    price_fmt = f"{last['price']:,}".replace(",", " ")
    await safe_edit(
        callback,
        f"🔁 *Быстрая перезапись*\n\n"
        f"Услуга: *{last['name']}*  —  {price_fmt} ₽\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📅 Выберите дату и время:",
        reply_markup=slots_keyboard(slots),
        parse_mode="Markdown"
    )
    await state.set_state(BookingStates.waiting_for_slot)
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ЗАПИСЬ — шаг 1: выбор услуги
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "book")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    services = await get_services()
    if not services:
        await callback.answer("Услуги временно не добавлены. Обратитесь к мастеру.", show_alert=True)
        return
    await safe_edit(
        callback,
        "💅 *Запись на маникюр*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Шаг *1 из 4*  —  Выберите услугу:",
        reply_markup=services_keyboard(services),
        parse_mode="Markdown"
    )
    await state.set_state(BookingStates.waiting_for_service)
    await callback.answer()

@router.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    services = await get_services()
    await safe_edit(
        callback,
        "💅 *Запись на маникюр*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Шаг *1 из 4*  —  Выберите услугу:",
        reply_markup=services_keyboard(services),
        parse_mode="Markdown"
    )
    await state.set_state(BookingStates.waiting_for_service)
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ЗАПИСЬ — шаг 2: выбор времени
# ════════════════════════════════════════════════════════

@router.callback_query(StateFilter(BookingStates.waiting_for_service), F.data.startswith("service_"))
async def process_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split("_")[1])
    service    = await get_service_by_id(service_id)
    await state.update_data(service_id=service_id)

    slots = await get_free_slots()
    if not slots:
        await callback.answer("Свободных слотов нет. Загляните позже.", show_alert=True)
        return

    price_fmt = f"{service['price']:,}".replace(",", " ") if service else ""
    await safe_edit(
        callback,
        f"💅 *Запись на маникюр*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ Услуга: *{service['name']}*  —  {price_fmt} ₽\n\n"
        f"Шаг *2 из 4*  —  Выберите дату и время:",
        reply_markup=slots_keyboard(slots),
        parse_mode="Markdown"
    )
    await state.set_state(BookingStates.waiting_for_slot)
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ЗАПИСЬ — шаг 3: имя  (с таймером бездействия)
# ════════════════════════════════════════════════════════

@router.callback_query(StateFilter(BookingStates.waiting_for_slot), F.data.startswith("slot_"))
async def process_slot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    slot_id = int(callback.data.split("_")[1])
    slot    = await get_slot_by_id(slot_id)
    await state.update_data(slot_id=slot_id)

    data      = await state.get_data()
    service   = await get_service_by_id(data.get('service_id'))
    dt        = slot['datetime'].replace('T', ' ')[:16] if slot else "—"
    price_fmt = f"{service['price']:,}".replace(",", " ") if service else ""

    await safe_edit(
        callback,
        f"💅 *Запись на маникюр*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ Услуга: *{service['name']}*  —  {price_fmt} ₽\n"
        f"✅ Время:  *{dt}*\n\n"
        f"Шаг *3 из 4*  —  Как вас зовут?\n\n"
        f"_Введите имя:_",
        parse_mode="Markdown"
    )
    await state.set_state(BookingStates.waiting_for_name)
    await callback.answer()

    # Таймер бездействия
    asyncio.create_task(idle_timer(bot, callback.message.chat.id, callback.from_user.id, state))


@router.message(StateFilter(BookingStates.waiting_for_name), F.text)
async def process_name(message: Message, state: FSMContext, bot: Bot):
    name = message.text.strip()
    if not name:
        await message.answer("Пожалуйста, введите ваше имя.")
        return
    await state.update_data(user_name=name)
    await message.answer(
        "📱 *Шаг 4 из 4*  —  Контакт для связи\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "• Нажмите кнопку ниже — поделитесь номером телефона\n"
        "• Или напишите Telegram username (например, `@username`)",
        parse_mode="Markdown",
        reply_markup=contact_keyboard()
    )
    await state.set_state(BookingStates.waiting_for_contact)

    # Таймер бездействия
    asyncio.create_task(idle_timer(bot, message.chat.id, message.from_user.id, state))


# ════════════════════════════════════════════════════════
#  ЗАПИСЬ — шаг 4: контакт
# ════════════════════════════════════════════════════════

@router.message(StateFilter(BookingStates.waiting_for_contact), F.contact)
async def process_contact_phone(message: Message, state: FSMContext):
    await state.update_data(contact=message.contact.phone_number)
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    await _show_confirmation(message, state)

@router.message(StateFilter(BookingStates.waiting_for_contact), F.text)
async def process_contact_text(message: Message, state: FSMContext):
    t = message.text.strip()
    if t.lstrip("+").replace(" ", "").replace("-", "").isdigit():
        contact = t
    elif t.startswith("@"):
        contact = t
    else:
        contact = f"@{t}"
    await state.update_data(contact=contact)
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    await _show_confirmation(message, state)


# ════════════════════════════════════════════════════════
#  ЗАПИСЬ — подтверждение
# ════════════════════════════════════════════════════════

async def _show_confirmation(message: Message, state: FSMContext):
    data    = await state.get_data()
    service = await get_service_by_id(data['service_id'])
    slot    = await get_slot_by_id(data['slot_id'])

    if not service or not slot:
        await message.answer(
            "⚠️ Ошибка данных. Попробуйте заново — /start",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return

    dt        = slot['datetime'].replace('T', ' ')[:16]
    price_fmt = f"{service['price']:,}".replace(",", " ")

    await message.answer(
        f"✅ *Проверьте данные:*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 *Имя:*      {data['user_name']}\n"
        f"📞 *Контакт:*  `{data['contact']}`\n"
        f"💅 *Услуга:*   {service['name']}  —  {price_fmt} ₽\n"
        f"📅 *Время:*    {dt}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"Всё верно?",
        parse_mode="Markdown",
        reply_markup=confirm_kb()
    )
    await state.set_state(BookingStates.confirm_booking)


@router.callback_query(StateFilter(BookingStates.confirm_booking), F.data == "confirm_yes")
async def confirm_booking_yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data      = await state.get_data()
    user      = callback.from_user
    tg_user   = f"@{user.username}" if user.username else ""
    service   = await get_service_by_id(data['service_id'])
    slot      = await get_slot_by_id(data['slot_id'])
    dt        = slot['datetime'].replace('T', ' ')[:16] if slot else "—"
    price_fmt = f"{service['price']:,}".replace(",", " ") if service else "—"

    await create_appointment(
        user_id=user.id,
        user_name=data['user_name'],
        tg_username=tg_user,
        contact=data['contact'],
        service_id=data['service_id'],
        slot_id=data['slot_id']
    )

    await callback.message.edit_text(
        f"🎉 *Вы записаны!*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💅 {service['name']}  —  {price_fmt} ₽\n"
        f"📅 {dt}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"Мастер *{MASTER_NAME}* свяжется с вами для подтверждения.\n"
        f"⏰ За 24 ч до визита пришлю напоминание 🔔",
        parse_mode="Markdown"
    )

    notify = (
        f"🔔 *Новая запись!*\n\n"
        f"👤 {data['user_name']}\n"
        f"🔗 {tg_user or '—'}\n"
        f"📞 `{data['contact']}`\n"
        f"💅 {service['name']}  —  {price_fmt} ₽\n"
        f"📅 {dt}"
    )
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, notify, parse_mode="Markdown")
        except Exception:
            pass

    await state.clear()
    await callback.message.answer(
        "🏠 *Главное меню*",
        parse_mode="Markdown",
        reply_markup=main_menu(user.id in ADMINS)
    )
    await callback.answer()


@router.callback_query(StateFilter(BookingStates.confirm_booking), F.data == "confirm_no")
async def confirm_booking_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✖️ Запись отменена.\n\nЕсли передумаете — нажмите «📅 Записаться».",
        reply_markup=main_menu(callback.from_user.id in ADMINS)
    )
    await callback.answer()