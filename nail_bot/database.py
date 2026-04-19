import aiosqlite
from typing import List, Dict, Optional

DB_PATH = "bot.db"


# ════════════════════════════════════════════
#  ИНИЦИАЛИЗАЦИЯ
# ════════════════════════════════════════════

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id          INTEGER PRIMARY KEY,
                name        TEXT    NOT NULL,
                price       INTEGER NOT NULL,
                description TEXT    DEFAULT ''
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS slots (
                id        INTEGER PRIMARY KEY,
                datetime  TEXT    UNIQUE NOT NULL,
                is_booked INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id           INTEGER PRIMARY KEY,
                user_id      INTEGER NOT NULL,
                user_name    TEXT    NOT NULL,
                tg_username  TEXT    DEFAULT '',
                contact      TEXT    NOT NULL,
                service_id   INTEGER NOT NULL,
                slot_id      INTEGER NOT NULL,
                status       TEXT    DEFAULT 'pending',
                reminded     INTEGER DEFAULT 0,
                review_asked INTEGER DEFAULT 0,
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (service_id) REFERENCES services(id),
                FOREIGN KEY (slot_id)    REFERENCES slots(id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id             INTEGER PRIMARY KEY,
                user_id        INTEGER NOT NULL,
                user_name      TEXT    NOT NULL,
                appointment_id INTEGER,
                rating         INTEGER NOT NULL,
                text           TEXT    DEFAULT '',
                created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id          INTEGER PRIMARY KEY,
                file_id     TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Безопасные миграции для старых БД
        for col, defn in [
            ("tg_username",  "TEXT DEFAULT ''"),
            ("reminded",     "INTEGER DEFAULT 0"),
            ("review_asked", "INTEGER DEFAULT 0"),
            ("status",       "TEXT DEFAULT 'pending'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE appointments ADD COLUMN {col} {defn}")
            except Exception:
                pass

        # Стартовые услуги
        cur = await db.execute("SELECT COUNT(*) FROM services")
        if (await cur.fetchone())[0] == 0:
            await db.executemany(
                "INSERT INTO services (name, price, description) VALUES (?, ?, ?)",
                [
                    ("Однотонное покрытие",   1800, "Любой цвет, без дизайна"),
                    ("Дизайн на 4 пальчиках",  300, "Простой дизайн"),
                    ("Френч",                 2000, "Классический или цветной"),
                ]
            )
        await db.commit()


# ════════════════════════════════════════════
#  УСЛУГИ
# ════════════════════════════════════════════

async def get_services() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM services ORDER BY price")
        return [dict(r) for r in await cur.fetchall()]

async def get_service_by_id(sid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM services WHERE id=?", (sid,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def add_service(name: str, price: int, description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO services (name, price, description) VALUES (?,?,?)",
            (name, price, description)
        )
        await db.commit()

async def delete_service(sid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id=?", (sid,))
        await db.commit()


# ════════════════════════════════════════════
#  СЛОТЫ
# ════════════════════════════════════════════

async def get_free_slots() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, datetime FROM slots "
            "WHERE is_booked=0 AND datetime > datetime('now','+3 hours') "
            "ORDER BY datetime"
        )
        return [dict(r) for r in await cur.fetchall()]

async def get_all_free_slots() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, datetime FROM slots WHERE is_booked=0 ORDER BY datetime"
        )
        return [dict(r) for r in await cur.fetchall()]

async def add_slot(dt_str: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO slots (datetime) VALUES (?)", (dt_str,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def delete_slot(slot_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT is_booked FROM slots WHERE id=?", (slot_id,))
        r = await cur.fetchone()
        if not r or r[0] == 1:
            return False
        await db.execute("DELETE FROM slots WHERE id=?", (slot_id,))
        await db.commit()
        return True

async def get_slot_by_id(slot_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM slots WHERE id=?", (slot_id,))
        r = await cur.fetchone()
        return dict(r) if r else None


# ════════════════════════════════════════════
#  ЗАПИСИ
# ════════════════════════════════════════════

async def create_appointment(
    user_id: int, user_name: str, tg_username: str,
    contact: str, service_id: int, slot_id: int
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO appointments "
            "(user_id,user_name,tg_username,contact,service_id,slot_id,status) "
            "VALUES (?,?,?,?,?,?,'pending')",
            (user_id, user_name, tg_username, contact, service_id, slot_id)
        )
        await db.execute("UPDATE slots SET is_booked=1 WHERE id=?", (slot_id,))
        await db.commit()
        return cur.lastrowid

async def get_user_appointments(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('''
            SELECT a.id, a.status, s.datetime, serv.name, serv.price
            FROM appointments a
            JOIN slots    s    ON a.slot_id    = s.id
            JOIN services serv ON a.service_id = serv.id
            WHERE a.user_id=? AND a.status != 'cancelled'
            ORDER BY s.datetime
        ''', (user_id,))
        return [dict(r) for r in await cur.fetchall()]

async def get_last_user_service(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('''
            SELECT serv.id, serv.name, serv.price
            FROM appointments a
            JOIN services serv ON a.service_id = serv.id
            WHERE a.user_id=?
            ORDER BY a.created_at DESC LIMIT 1
        ''', (user_id,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def get_all_appointments() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('''
            SELECT a.id, a.user_id, a.user_name, a.tg_username,
                   a.contact, a.status, s.datetime, serv.name, serv.price
            FROM appointments a
            JOIN slots    s    ON a.slot_id    = s.id
            JOIN services serv ON a.service_id = serv.id
            WHERE a.status != 'cancelled'
            ORDER BY s.datetime
        ''')
        return [dict(r) for r in await cur.fetchall()]

async def confirm_appointment(apt_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status='confirmed' WHERE id=?", (apt_id,)
        )
        await db.commit()

async def cancel_appointment(apt_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT slot_id FROM appointments WHERE id=?", (apt_id,))
        r = await cur.fetchone()
        if r:
            await db.execute("UPDATE slots SET is_booked=0 WHERE id=?", (r[0],))
            await db.execute(
                "UPDATE appointments SET status='cancelled' WHERE id=?", (apt_id,)
            )
            await db.commit()

async def get_appointments_for_review(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('''
            SELECT a.id, a.user_id, a.user_name, serv.name
            FROM appointments a
            JOIN slots s ON a.slot_id = s.id
            JOIN services serv ON a.service_id = serv.id
            LEFT JOIN reviews r ON r.appointment_id = a.id
            WHERE a.user_id = ?
              AND r.id IS NULL
              AND a.status = 'confirmed'
              AND replace(s.datetime, 'T', ' ') < datetime('now')
            LIMIT 1
        ''', (user_id,))
        return [dict(r) for r in await cur.fetchall()]

async def get_all_appointments_for_review_bot() -> List[Dict]:
    """Для планировщика: все клиенты с незапрошенным отзывом."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('''
            SELECT a.id, a.user_id, a.user_name, serv.name
            FROM appointments a
            JOIN slots    s    ON a.slot_id    = s.id
            JOIN services serv ON a.service_id = serv.id
            LEFT JOIN reviews r ON r.appointment_id = a.id
            WHERE a.status IN ('confirmed','pending')
              AND s.datetime < datetime('now')
              AND s.datetime > datetime('now', '-48 hours')
              AND a.review_asked = 0
              AND r.id IS NULL
        ''')
        return [dict(r) for r in await cur.fetchall()]

async def mark_review_asked(apt_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET review_asked=1 WHERE id=?", (apt_id,)
        )
        await db.commit()


# ════════════════════════════════════════════
#  ОТЗЫВЫ
# ════════════════════════════════════════════

async def add_review(user_id: int, user_name: str, apt_id: int, rating: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reviews (user_id,user_name,appointment_id,rating,text) VALUES (?,?,?,?,?)",
            (user_id, user_name, apt_id, rating, text)
        )
        await db.commit()

async def get_reviews(limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]

async def get_average_rating() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT AVG(rating) FROM reviews")
        v = (await cur.fetchone())[0]
        return round(v, 1) if v else 0.0


# ════════════════════════════════════════════
#  ПОРТФОЛИО
# ════════════════════════════════════════════

async def add_portfolio_photo(file_id: str, description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO portfolio (file_id, description) VALUES (?,?)",
            (file_id, description)
        )
        await db.commit()

async def get_portfolio() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM portfolio ORDER BY created_at DESC")
        return [dict(r) for r in await cur.fetchall()]

async def delete_portfolio_photo(photo_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM portfolio WHERE id=?", (photo_id,))
        await db.commit()


# ════════════════════════════════════════════
#  СТАТИСТИКА
# ════════════════════════════════════════════

async def get_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async def scalar(sql, params=()):
            c = await db.execute(sql, params)
            r = await c.fetchone()
            return r[0] if r else 0

        total_active  = await scalar("SELECT COUNT(*) FROM appointments WHERE status!='cancelled'")
        month_count   = await scalar(
            "SELECT COUNT(*) FROM appointments WHERE status!='cancelled' "
            "AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')"
        )
        month_revenue = await scalar('''
            SELECT COALESCE(SUM(serv.price),0)
            FROM appointments a JOIN services serv ON a.service_id=serv.id
            WHERE a.status!='cancelled'
              AND strftime('%Y-%m',a.created_at)=strftime('%Y-%m','now')
        ''')
        total_clients = await scalar("SELECT COUNT(DISTINCT user_id) FROM appointments")
        free_slots    = await scalar(
            "SELECT COUNT(*) FROM slots WHERE is_booked=0 AND datetime>datetime('now')"
        )
        avg_r         = await scalar("SELECT AVG(rating) FROM reviews")
        review_count  = await scalar("SELECT COUNT(*) FROM reviews")

        cur = await db.execute('''
            SELECT serv.name, COUNT(*) c
            FROM appointments a JOIN services serv ON a.service_id=serv.id
            WHERE a.status!='cancelled'
            GROUP BY a.service_id ORDER BY c DESC LIMIT 1
        ''')
        top = await cur.fetchone()
        top_service = f"{top[0]} ({top[1]} раз)" if top else "—"

        return {
            "total_active":  total_active,
            "month_count":   month_count,
            "month_revenue": month_revenue,
            "total_clients": total_clients,
            "free_slots":    free_slots,
            "avg_rating":    round(avg_r, 1) if avg_r else 0.0,
            "review_count":  review_count,
            "top_service":   top_service,
        }


# ════════════════════════════════════════════
#  РАССЫЛКА / НАПОМИНАНИЯ
# ════════════════════════════════════════════

async def get_all_clients() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT DISTINCT user_id, user_name, tg_username FROM appointments"
        )
        return [dict(r) for r in await cur.fetchall()]

async def get_upcoming_for_reminder() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('''
            SELECT a.id, a.user_id, a.user_name, s.datetime, serv.name
            FROM appointments a
            JOIN slots    s    ON a.slot_id    = s.id
            JOIN services serv ON a.service_id = serv.id
            WHERE a.status != 'cancelled'
              AND a.reminded  = 0
              AND s.datetime  > datetime('now', '+23 hours')
              AND s.datetime  < datetime('now', '+25 hours')
        ''')
        return [dict(r) for r in await cur.fetchall()]

async def mark_reminded(apt_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE appointments SET reminded=1 WHERE id=?", (apt_id,))
        await db.commit()