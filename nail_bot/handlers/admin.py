from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from config import ADMINS
from database import (
    get_all_appointments, cancel_appointment, confirm_appointment,
    add_service, delete_service, get_services,
    add_slot, delete_slot, get_all_free_slots,
    get_stats, get_all_clients,
    get_portfolio, add_portfolio_photo, delete_portfolio_photo,
    get_reviews,
)
from keyboards import (
    admin_panel_kb, admin_slots_kb, admin_services_kb,
    admin_portfolio_kb, back_admin_kb, cancel_kb,
)
from states import AdminStates

router = Router()


def is_admin(uid: int) -> bool:
    return uid in ADMINS


# ────────────────────────────────────────────
#  Вспомогательная: безопасный edit (для фото-сообщений)
# ────────────────────────────────────────────
async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None, **kw):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, **kw)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, **kw)


# ════════════════════════════════════════════════════════
#  ГЛАВНАЯ ПАНЕЛЬ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await state.clear()
    s = await get_stats()
    text = (
        f"⚙️ *Панель управления*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📋 Активных записей:  *{s['total_active']}*\n"
        f"📅 За этот месяц:     *{s['month_count']}* — {s['month_revenue']} ₽\n"
        f"⭐ Рейтинг:           *{s['avg_rating']}* / 5.0  ({s['review_count']} отз.)\n"
        f"🕐 Свободных слотов:  *{s['free_slots']}*\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(callback, text, reply_markup=admin_panel_kb(), parse_mode="Markdown")
    await callback.answer()


# ════════════════════════════════════════════════════════
#  СТАТИСТИКА
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    s = await get_stats()
    text = (
        f"📊 *Подробная статистика*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📋 Активных записей:    *{s['total_active']}*\n"
        f"📅 Записей за месяц:    *{s['month_count']}*\n"
        f"💰 Выручка за месяц:   *{s['month_revenue']} ₽*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего клиентов:      *{s['total_clients']}*\n"
        f"🏆 Популярная услуга:   *{s['top_service']}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⭐ Средний рейтинг:    *{s['avg_rating']}* / 5.0\n"
        f"💬 Всего отзывов:       *{s['review_count']}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕐 Свободных слотов:   *{s['free_slots']}*"
    )
    await safe_edit(callback, text, reply_markup=back_admin_kb(), parse_mode="Markdown")
    await callback.answer()


# ════════════════════════════════════════════════════════
#  ЗАПИСИ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_appointments")
async def admin_appointments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    apts = await get_all_appointments()
    ICON = {"pending": "🕐", "confirmed": "✅"}

    if not apts:
        await safe_edit(
            callback, "📭 Активных записей нет.",
            reply_markup=back_admin_kb(), parse_mode="Markdown"
        )
        await callback.answer()
        return

    lines   = [f"📋 *Записи ({len(apts)}):*\n", "━━━━━━━━━━━━━━━━━"]
    buttons = []
    for i, a in enumerate(apts, 1):
        dt   = a['datetime'].replace('T', ' ')[:16]
        icon = ICON.get(a['status'], "📋")
        tg   = a.get('tg_username') or '—'
        lines.append(
            f"\n{icon} *{i}. {a['user_name']}*\n"
            f"     🔗 {tg}  •  📞 `{a['contact']}`\n"
            f"     💅 {a['name']}  —  {a['price']} ₽\n"
            f"     📅 {dt}"
        )
        row = []
        if a['status'] == 'pending':
            row.append(InlineKeyboardButton(
                text=f"✅ №{a['id']}", callback_data=f"aok_{a['id']}"
            ))
        row.append(InlineKeyboardButton(
            text=f"❌ №{a['id']}", callback_data=f"adel_{a['id']}"
        ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")])
    await safe_edit(
        callback, "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aok_"))
async def admin_confirm_apt(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    apt_id = int(callback.data.split("_")[1])
    apts   = await get_all_appointments()
    apt    = next((a for a in apts if a['id'] == apt_id), None)
    await confirm_appointment(apt_id)
    if apt:
        dt = apt['datetime'].replace('T', ' ')[:16]
        try:
            await bot.send_message(
                apt['user_id'],
                f"✅ *Ваша запись подтверждена!*\n\n"
                f"💅 {apt['name']}\n📅 {dt}\n\nЖдём вас! 💕",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await callback.answer("✅ Подтверждена, клиент уведомлён", show_alert=True)
    await admin_appointments(callback)


@router.callback_query(F.data.startswith("adel_"))
async def admin_cancel_apt(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    apt_id = int(callback.data.split("_")[1])
    apts   = await get_all_appointments()
    apt    = next((a for a in apts if a['id'] == apt_id), None)
    await cancel_appointment(apt_id)
    if apt:
        dt = apt['datetime'].replace('T', ' ')[:16]
        try:
            await bot.send_message(
                apt['user_id'],
                f"❌ *Ваша запись отменена мастером*\n\n"
                f"💅 {apt['name']}\n📅 {dt}\n\nДля перезаписи — /start",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await callback.answer("❌ Отменена, клиент уведомлён", show_alert=True)
    await admin_appointments(callback)


# ════════════════════════════════════════════════════════
#  СЛОТЫ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_slots_menu")
async def admin_slots_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.clear()
    slots = await get_all_free_slots()
    await safe_edit(
        callback,
        f"🗓 *Управление слотами*\n\nСвободных слотов: *{len(slots)}*",
        reply_markup=admin_slots_kb(), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_slot")
async def admin_add_slot_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(
        callback,
        "📅 *Добавить слот*\n\n"
        "Формат: `ГГГГ-ММ-ДД ЧЧ:ММ`\n"
        "Пример: `2025-06-15 14:00`",
        reply_markup=cancel_kb("admin_slots_menu"), parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_slot_datetime)
    await callback.answer()

@router.message(AdminStates.waiting_for_slot_datetime)
async def admin_add_slot_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    import re
    s = message.text.strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', s):
        await message.answer("❌ Неверный формат.\nПример: `2025-06-15 14:00`", parse_mode="Markdown")
        return
    ok = await add_slot(s)
    await state.clear()
    result = f"✅ Слот *{s}* добавлен!" if ok else f"⚠️ Слот *{s}* уже существует."
    await message.answer(result, parse_mode="Markdown", reply_markup=admin_slots_kb())


@router.callback_query(F.data == "admin_bulk_slots")
async def admin_bulk_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(
        callback,
        "📆 *Добавить неделю слотов*\n\n"
        "Формат: `ГГГГ-ММ-ДД ЧЧ:ММ-ЧЧ:ММ ШАГ`\n\n"
        "Пример: `2025-06-16 10:00-18:00 60`\n"
        "_Создаст слоты каждый час с 10:00 до 18:00 на 7 дней подряд_\n\n"
        "ШАГ в минутах: 30 / 60 / 90 / 120",
        reply_markup=cancel_kb("admin_slots_menu"), parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_bulk_slot)
    await callback.answer()

@router.message(AdminStates.waiting_for_bulk_slot)
async def admin_bulk_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    import re
    from datetime import datetime, timedelta

    m = re.match(r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})-(\d{2}:\d{2}) (\d+)$', message.text.strip())
    if not m:
        await message.answer("❌ Неверный формат.\nПример: `2025-06-16 10:00-18:00 60`", parse_mode="Markdown")
        return

    date_s, t0, t1, step_s = m.groups()
    step = int(step_s)
    if not (15 <= step <= 480):
        await message.answer("❌ Шаг: от 15 до 480 минут.")
        return

    added = skipped = 0
    for d in range(7):
        base = datetime.strptime(date_s, "%Y-%m-%d") + timedelta(days=d)
        cur  = datetime.strptime(f"{base:%Y-%m-%d} {t0}", "%Y-%m-%d %H:%M")
        end  = datetime.strptime(f"{base:%Y-%m-%d} {t1}", "%Y-%m-%d %H:%M")
        while cur < end:
            ok = await add_slot(cur.strftime("%Y-%m-%d %H:%M"))
            added += ok; skipped += not ok
            cur += timedelta(minutes=step)

    await state.clear()
    await message.answer(
        f"✅ *Готово!*\n\n➕ Добавлено: *{added}*\n⏭ Пропущено: *{skipped}*",
        parse_mode="Markdown", reply_markup=admin_slots_kb()
    )


@router.callback_query(F.data == "admin_delete_slot")
async def admin_delete_slot_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    slots = await get_all_free_slots()
    if not slots:
        await callback.answer("Нет свободных слотов", show_alert=True)
        return
    rows = [
        [InlineKeyboardButton(
            text=f"🗑  {s['datetime'].replace('T',' ')[:16]}",
            callback_data=f"ds_{s['id']}"
        )] for s in slots[:24]
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_slots_menu")])
    await safe_edit(
        callback, "🗑 *Удалить слот*\n\nВыберите:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_delete_slot)
    await callback.answer()

@router.callback_query(AdminStates.waiting_for_delete_slot, F.data.startswith("ds_"))
async def admin_delete_slot_confirm(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[1])
    ok = await delete_slot(slot_id)
    await state.clear()
    await callback.answer("✅ Удалён" if ok else "⚠️ Занят или не найден", show_alert=True)
    slots = await get_all_free_slots()
    await safe_edit(
        callback,
        f"🗓 *Управление слотами*\n\nСвободных слотов: *{len(slots)}*",
        reply_markup=admin_slots_kb(), parse_mode="Markdown"
    )


# ════════════════════════════════════════════════════════
#  УСЛУГИ
# ════════════════════════════════════════════════════════

async def _show_services(target, edit=True):
    services = await get_services()
    lines = ["💅 *Управление услугами*\n", "━━━━━━━━━━━━━━━━━"]
    if services:
        for s in services:
            p = f"{s['price']:,}".replace(",", " ")
            lines.append(f"• *{s['name']}*  —  {p} ₽")
            if s.get('description'):
                lines.append(f"  _{s['description']}_")
    else:
        lines.append("_Услуги не добавлены._")
    text = "\n".join(lines)
    kb   = admin_services_kb()
    if isinstance(target, CallbackQuery):
        if edit:
            await safe_edit(target, text, reply_markup=kb, parse_mode="Markdown")
        else:
            await target.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "admin_services")
async def admin_services_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await _show_services(callback, edit=True)
    await callback.answer()

@router.callback_query(F.data == "admin_add_service")
async def admin_add_svc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(
        callback, "➕ *Добавить услугу*\n\nВведите *название*:",
        reply_markup=cancel_kb("admin_services"), parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_service_name)
    await callback.answer()

@router.message(AdminStates.waiting_for_service_name)
async def admin_svc_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(svc_name=message.text.strip())
    await message.answer("Введите *цену* (только число, например `1800`):", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_service_price)

@router.message(AdminStates.waiting_for_service_price)
async def admin_svc_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        await state.update_data(svc_price=int(message.text.strip()))
        await message.answer("Введите *описание* (или `-` для пропуска):", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_service_desc)
    except ValueError:
        await message.answer("❌ Введите число:")

@router.message(AdminStates.waiting_for_service_desc)
async def admin_svc_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await add_service(data['svc_name'], data['svc_price'], desc)
    await state.clear()
    await message.answer(f"✅ Услуга *«{data['svc_name']}»* добавлена!", parse_mode="Markdown")
    await _show_services(message)

@router.callback_query(F.data == "admin_delete_service")
async def admin_del_svc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    services = await get_services()
    if not services:
        await callback.answer("Нет услуг", show_alert=True)
        return
    rows = [
        [InlineKeyboardButton(
            text=f"🗑  {s['name']}  ({s['price']} ₽)",
            callback_data=f"dsvc_{s['id']}"
        )] for s in services
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_services")])
    await safe_edit(
        callback, "🗑 Выберите услугу для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await state.set_state(AdminStates.waiting_for_delete_service)
    await callback.answer()

@router.callback_query(AdminStates.waiting_for_delete_service, F.data.startswith("dsvc_"))
async def admin_del_svc_confirm(callback: CallbackQuery, state: FSMContext):
    await delete_service(int(callback.data.split("_")[1]))
    await state.clear()
    await callback.answer("✅ Услуга удалена", show_alert=True)
    await _show_services(callback, edit=True)


# ════════════════════════════════════════════════════════
#  ПОРТФОЛИО
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_portfolio")
async def admin_portfolio(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.clear()
    photos = await get_portfolio()
    await safe_edit(
        callback,
        f"🖼 *Управление портфолио*\n\nФотографий: *{len(photos)}*",
        reply_markup=admin_portfolio_kb(), parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "admin_add_photo")
async def admin_add_photo_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(
        callback, "🖼 *Добавить фото*\n\nОтправьте фотографию работы:",
        reply_markup=cancel_kb("admin_portfolio"), parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_portfolio_photo)
    await callback.answer()

@router.message(AdminStates.waiting_for_portfolio_photo, F.photo)
async def admin_add_photo_recv(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(pf_file_id=message.photo[-1].file_id)
    await message.answer(
        "✅ Фото получено!\n\nДобавьте *подпись* к работе (или `-` для пропуска):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_portfolio_desc)

@router.message(AdminStates.waiting_for_portfolio_desc)
async def admin_add_photo_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await add_portfolio_photo(data['pf_file_id'], desc)
    await state.clear()
    photos = await get_portfolio()
    await message.answer(
        f"✅ Фото добавлено!\n\nВсего в портфолио: *{len(photos)}*",
        parse_mode="Markdown", reply_markup=admin_portfolio_kb()
    )

@router.callback_query(F.data == "admin_delete_photo")
async def admin_del_photo(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    photos = await get_portfolio()
    if not photos:
        await callback.answer("Портфолио пустое", show_alert=True)
        return
    rows = [
        [InlineKeyboardButton(
            text=f"🗑  #{p['id']}  {p.get('description','') or '(без подписи)'}",
            callback_data=f"dp_{p['id']}"
        )] for p in photos
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_portfolio")])
    await safe_edit(
        callback, "🗑 Выберите фото для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("dp_"))
async def admin_del_photo_confirm(callback: CallbackQuery):
    await delete_portfolio_photo(int(callback.data.split("_")[1]))
    await callback.answer("✅ Фото удалено", show_alert=True)
    photos = await get_portfolio()
    await safe_edit(
        callback,
        f"🖼 *Управление портфолио*\n\nФотографий: *{len(photos)}*",
        reply_markup=admin_portfolio_kb(), parse_mode="Markdown"
    )


# ════════════════════════════════════════════════════════
#  ОТЗЫВЫ
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_reviews")
async def admin_reviews_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    reviews = await get_reviews(limit=15)
    STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}
    if not reviews:
        await safe_edit(callback, "⭐ Отзывов пока нет.", reply_markup=back_admin_kb())
        await callback.answer()
        return
    lines = [f"⭐ *Отзывы клиентов ({len(reviews)}):*\n", "━━━━━━━━━━━━━━━━━"]
    for r in reviews:
        lines.append(f"\n{STARS.get(r['rating'],'?')} *{r['user_name']}*  •  {r['created_at'][:10]}")
        if r.get('text'):
            lines.append(f"_{r['text']}_")
    await safe_edit(
        callback, "\n".join(lines),
        reply_markup=back_admin_kb(), parse_mode="Markdown"
    )
    await callback.answer()


# ════════════════════════════════════════════════════════
#  РАССЫЛКА
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    clients = await get_all_clients()
    await safe_edit(
        callback,
        f"📣 *Рассылка*\n\n"
        f"Получателей: *{len(clients)}*\n\n"
        f"Напишите текст. Поддерживается *жирный*, _курсив_, `моноширинный`.",
        reply_markup=cancel_kb("admin_panel"), parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    clients = await get_all_clients()
    await state.clear()
    if not clients:
        await message.answer("📭 Нет клиентов.", reply_markup=admin_panel_kb())
        return

    text       = f"📢 *Сообщение от мастера:*\n\n{message.text}"
    status_msg = await message.answer(f"⏳ Отправляю... (0/{len(clients)})")
    sent = failed = 0

    for i, c in enumerate(clients, 1):
        try:
            await bot.send_message(c['user_id'], text, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
        if i % 5 == 0 or i == len(clients):
            try:
                await status_msg.edit_text(f"⏳ Отправляю... ({i}/{len(clients)})")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ *Рассылка завершена!*\n\n✉️ Отправлено: *{sent}*\n❌ Ошибок: *{failed}*",
        parse_mode="Markdown"
    )
    await message.answer("⚙️ *Панель управления*", parse_mode="Markdown", reply_markup=admin_panel_kb())