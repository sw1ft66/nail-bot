"""
keyboards.py  —  все клавиатуры бота.
Принципы дизайна:
  • Симметричные 2-колоночные сетки там где возможно
  • «Назад» всегда последним на всю ширину
  • Эмодзи несут смысловую нагрузку, не декор
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import MASTER_TG, SUPPORT_USERNAME
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import MASTER_PHONE, MASTER_NAME
# ════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ════════════════════════════════════════════

def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📅 Записаться",  callback_data="book"),
            InlineKeyboardButton(text="💰 Цены",        callback_data="prices"),
        ],
        [
            InlineKeyboardButton(text="🖼 Портфолио",   callback_data="portfolio"),
            InlineKeyboardButton(text="⭐ Отзывы",      callback_data="reviews"),
        ],
        [
            InlineKeyboardButton(text="📋 Мои записи",  callback_data="my_appointments"),
            InlineKeyboardButton(text="📞 Контакты",    callback_data="contacts"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙️ Панель управления", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════
#  КЛИЕНТСКИЕ РАЗДЕЛЫ
# ════════════════════════════════════════════

def prices_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться",   callback_data="book")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")],
    ])

def back_main_kb() -> InlineKeyboardMarkup:
    """Одна кнопка «Назад» — универсальная."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")]
    ])

def contacts_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✈️ Написать мастеру", url=f"https://t.me/{MASTER_TG.replace('@','')}")],
        [InlineKeyboardButton(text="🛠 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")]
    ])

def reviews_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")]
    ])


# ════════════════════════════════════════════
#  ЗАПИСЬ — услуги
# ════════════════════════════════════════════

def services_keyboard(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        price_fmt = f"{s['price']:,}".replace(",", " ")
        builder.button(
            text=f"💅  {s['name']}  —  {price_fmt} ₽",
            callback_data=f"service_{s['id']}"
        )
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


# ════════════════════════════════════════════
#  ЗАПИСЬ — слоты (красивый формат даты)
# ════════════════════════════════════════════

def slots_keyboard(slots: list) -> InlineKeyboardMarkup:
    from datetime import datetime
    DAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    builder = InlineKeyboardBuilder()
    for slot in slots:
        raw = slot['datetime'].replace('T', ' ')
        try:
            dt  = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
            day = DAYS_RU[dt.weekday()]
            label = f"📅  {dt.strftime('%d.%m')} ({day})  •  {dt.strftime('%H:%M')}"
        except Exception:
            label = f"📅  {raw[:16]}"
        builder.button(text=label, callback_data=f"slot_{slot['id']}")
    builder.button(text="◀️ Назад к услугам", callback_data="back_to_services")
    builder.adjust(1)
    return builder.as_markup()


# ════════════════════════════════════════════
#  ЗАПИСЬ — подтверждение
# ════════════════════════════════════════════

def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, записаться!", callback_data="confirm_yes"),
            InlineKeyboardButton(text="✖️ Отмена",          callback_data="confirm_no"),
        ]
    ])


# ════════════════════════════════════════════
#  КОНТАКТ (reply-keyboard для телефона)
# ════════════════════════════════════════════

def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="📱 Поделиться номером телефона",
            request_contact=True
        )]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ════════════════════════════════════════════
#  МОИ ЗАПИСИ
# ════════════════════════════════════════════

def my_appointments_kb(appointments: list) -> InlineKeyboardMarkup:
    rows = []
    for apt in appointments:
        dt = apt['datetime'].replace('T', ' ')[:16]
        rows.append([InlineKeyboardButton(
            text=f"❌  Отменить: {dt}",
            callback_data=f"cancel_apt_{apt['id']}"
        )])
    rows.append([InlineKeyboardButton(
        text="🔁 Повторить последнюю запись",
        callback_data="quick_rebook"
    )])
    rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════
#  ПОРТФОЛИО — навигация (листалка)
# ════════════════════════════════════════════

def portfolio_nav_kb(current: int, total: int) -> InlineKeyboardMarkup:
    nav = []
    if current > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"pf_{current - 1}"))
    nav.append(InlineKeyboardButton(text=f"· {current + 1} / {total} ·", callback_data="noop"))
    if current < total - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"pf_{current + 1}"))

    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [
            InlineKeyboardButton(text="📅 Записаться",   callback_data="book"),
            InlineKeyboardButton(text="◀️ Меню",         callback_data="pf_back"),
        ],
    ])

def portfolio_empty_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться",   callback_data="book")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")],
    ])


# ════════════════════════════════════════════
#  ОТЗЫВЫ — звёздная оценка
# ════════════════════════════════════════════

def rating_kb(apt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐",     callback_data=f"rate_{apt_id}_1"),
            InlineKeyboardButton(text="⭐⭐",   callback_data=f"rate_{apt_id}_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_{apt_id}_3"),
        ],
        [
            InlineKeyboardButton(text="⭐⭐⭐⭐",   callback_data=f"rate_{apt_id}_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_{apt_id}_5"),
        ],
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_review")],
    ])

def skip_text_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_review_text")]
    ])


# ════════════════════════════════════════════
#  ADMIN-ПАНЕЛЬ
# ════════════════════════════════════════════

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Записи",     callback_data="admin_appointments"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton(text="🗓 Слоты",      callback_data="admin_slots_menu"),
            InlineKeyboardButton(text="💅 Услуги",     callback_data="admin_services"),
        ],
        [
            InlineKeyboardButton(text="🖼 Портфолио",  callback_data="admin_portfolio"),
            InlineKeyboardButton(text="⭐ Отзывы",     callback_data="admin_reviews"),
        ],
        [InlineKeyboardButton(text="📣 Рассылка",      callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="◀️ Главное меню",  callback_data="back_to_main")],
    ])

def admin_slots_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить один слот",     callback_data="admin_add_slot")],
        [InlineKeyboardButton(text="📆 Добавить неделю слотов", callback_data="admin_bulk_slots")],
        [InlineKeyboardButton(text="🗑 Удалить свободный слот", callback_data="admin_delete_slot")],
        [InlineKeyboardButton(text="◀️ Назад",                  callback_data="admin_panel")],
    ])

def admin_services_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить услугу", callback_data="admin_add_service")],
        [InlineKeyboardButton(text="🗑 Удалить услугу",  callback_data="admin_delete_service")],
        [InlineKeyboardButton(text="◀️ Назад",           callback_data="admin_panel")],
    ])

def admin_portfolio_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить фото", callback_data="admin_add_photo")],
        [InlineKeyboardButton(text="🗑 Удалить фото",  callback_data="admin_delete_photo")],
        [InlineKeyboardButton(text="◀️ Назад",         callback_data="admin_panel")],
    ])

def back_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")]
    ])

def cancel_kb(cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖️ Отмена", callback_data=cb)]
    ])
    