from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    waiting_for_service = State()
    waiting_for_slot    = State()
    waiting_for_name    = State()
    waiting_for_contact = State()
    confirm_booking     = State()


class ReviewStates(StatesGroup):
    waiting_for_rating  = State()   # выбор звёзд
    waiting_for_text    = State()   # текст отзыва


class AdminStates(StatesGroup):
    # Слоты
    waiting_for_slot_datetime  = State()
    waiting_for_bulk_slot      = State()
    waiting_for_delete_slot    = State()
    # Услуги
    waiting_for_service_name   = State()
    waiting_for_service_price  = State()
    waiting_for_service_desc   = State()
    waiting_for_delete_service = State()
    # Портфолио
    waiting_for_portfolio_photo = State()
    waiting_for_portfolio_desc  = State()
    # Рассылка
    waiting_for_broadcast_text  = State()