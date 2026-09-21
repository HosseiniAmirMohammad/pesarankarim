import asyncio
import importlib.util
import os
import sqlite3
import tempfile
import types
from unittest.mock import AsyncMock

BASE = os.path.dirname(os.path.abspath(__file__))

# ===== دیتابیس تست (فایل موقت) =====
# از یک فایل موقت استفاده می‌کنیم تا داده‌های واقعی pesarankarim.db دست نخورد
import database as db_module

TMP_DB = os.path.join(tempfile.gettempdir(), "pesarankarim_validate_user_log.db")
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
db_module.DB_PATH = TMP_DB

# ===== بارگذاری ماژول اصلی ربات =====
spec = importlib.util.spec_from_file_location(
    "pesarankarim_mod", os.path.join(BASE, "pesarankarim.py")
)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

bot.real_member = AsyncMock(return_value=True)

OWNER = bot.OWNER_ID
CUSTOMER = 900907001
SECOND_CUSTOMER = 900907002
REGULAR_USER = 900907003

RESULTS = []


def check(name, condition, extra=""):
    RESULTS.append(bool(condition))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  ->  {extra}" if extra else ""))


class FakeMessage:
    def __init__(self, text=None):
        self.text = text
        self.reply_text = AsyncMock()
        self.chat_id = 1


class FakeUser:
    def __init__(self, user_id, first_name="کاربر تست", username=None):
        self.id = user_id
        self.first_name = first_name
        self.last_name = None
        self.username = username


def make_update(user, text=None):
    return types.SimpleNamespace(
        effective_user=user,
        message=FakeMessage(text),
        callback_query=None,
    )


def make_context(user_data=None):
    return types.SimpleNamespace(
        user_data=user_data if user_data is not None else {},
        bot=types.SimpleNamespace(
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_document=AsyncMock(),
            delete_message=AsyncMock(),
            get_chat_member=AsyncMock(),
        ),
    )


def fetch_rows(table, order_by="rowid"):
    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}")
    ]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# ۱) ساخت جداول کاربران و لاگ استفاده
# ---------------------------------------------------------------------------
print("\n=== ۱) ساخت جداول کاربران ربات و لاگ استفاده ===")

db_module.init_db()
db_module.init_admin_user()

conn = sqlite3.connect(TMP_DB)
tables = {
    row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
}
conn.close()

check("جدول users ساخته شد", "users" in tables)
check("جدول usage_logs ساخته شد", "usage_logs" in tables)

# ---------------------------------------------------------------------------
# ۲) ثبت کاربر و تاریخ عضویت
# ---------------------------------------------------------------------------
print("\n=== ۲) ثبت تاریخ عضویت کاربر در ربات ===")

first_record = db_module.register_user(
    CUSTOMER, username="customer_test", first_name="علی", last_name="تستی"
)
check("کاربر در جدول users ثبت شد", bool(first_record))
check(
    "تاریخ عضویت (joined_at) ثبت شد",
    bool(first_record and first_record["joined_at"]),
    str(first_record),
)
check(
    "اطلاعات کاربر ذخیره شد",
    first_record["username"] == "customer_test" and first_record["first_name"] == "علی",
)

# ثبت دوباره نباید تاریخ عضویت را تغییر دهد (فقط بروزرسانی اطلاعات)
conn = sqlite3.connect(TMP_DB)
joined_before = conn.execute(
    "SELECT joined_at FROM users WHERE user_id = ?", (CUSTOMER,)
).fetchone()[0]
conn.close()

second_record = db_module.register_user(CUSTOMER, username="customer_new")
check(
    "ثبت دوباره تاریخ عضویت قبلی را تغییر نمی‌دهد",
    second_record["joined_at"] == joined_before,
    f"{joined_before} -> {second_record['joined_at']}",
)
check(
    "اطلاعات کاربر در استفاده‌های بعدی بروزرسانی می‌شود",
    second_record["username"] == "customer_new",
)

# ---------------------------------------------------------------------------
# ۳) ثبت لاگ استفاده از ربات
# ---------------------------------------------------------------------------
print("\n=== ۳) ثبت لاگ استفاده از ربات ===")

db_module.log_bot_usage(CUSTOMER, "تست دستی اکشن", detail="جزئیات تست", first_name="علی")
logs = fetch_rows("usage_logs", "id DESC")
check("لاگ استفاده در جدول usage_logs ثبت شد", len(logs) == 1)
check(
    "اکشن و جزئیات لاگ ذخیره شد",
    logs[0]["action"] == "تست دستی اکشن" and logs[0]["detail"] == "جزئیات تست",
)
check("شناسه کاربر در لاگ ذخیره شد", logs[0]["user_id"] == CUSTOMER)

conn = sqlite3.connect(TMP_DB)
usage_count = conn.execute(
    "SELECT usage_count FROM users WHERE user_id = ?", (CUSTOMER,)
).fetchone()[0]
conn.close()
check("شمارنده استفاده کاربر افزایش یافت", usage_count == 1, f"usage_count={usage_count}")

# کاربر جدیدی که تا حالا ثبت نشده، با اولین استفاده به عنوان عضو ربات ثبت می‌شود
db_module.log_bot_usage(SECOND_CUSTOMER, "اولین استفاده", first_name="رضا")
all_users = db_module.get_users_log(limit=50)
second_user_row = next(
    (u for u in all_users if u["user_id"] == SECOND_CUSTOMER), None
)
check(
    "کاربر جدید با اولین استفاده به عنوان عضو ربات ثبت شد",
    bool(second_user_row and second_user_row["joined_at"]),
)

# ---------------------------------------------------------------------------
# ۴) خواندن لاگ‌ها به همراه تاریخ عضویت
# ---------------------------------------------------------------------------
print("\n=== ۴) خواندن لاگ‌ها همراه با تاریخ عضویت کاربر ===")

usage_rows = db_module.get_usage_logs(limit=10)
check(
    "لاگ‌ها همراه با joined_at برگردانده می‌شوند",
    all(row["joined_at"] for row in usage_rows),
)
check("تعداد کل لاگ‌ها درست است", db_module.get_usage_logs_count() == 2)

stats = db_module.get_users_stats()
check("آمار کاربران درست است", stats["total_users"] == 2, str(stats))
check("آمار کل استفاده‌ها درست است", stats["total_usage"] == 2, str(stats))
check("استفاده امروز محاسبه شد", stats["usage_today"] == 2, str(stats))

# ---------------------------------------------------------------------------
# ۵) تبدیل تاریخ به شمسی و به وقت ایران
# ---------------------------------------------------------------------------
print("\n=== ۵) نمایش تاریخ عضویت به صورت شمسی ===")

check(
    "تبدیل زمان UTC دیتابیس به وقت ایران درست است",
    bot.format_persian_datetime("2026-09-21 12:00:00") == "1405/06/30 - 15:30",
    bot.format_persian_datetime("2026-09-21 12:00:00"),
)
check(
    "نمایش فقط تاریخ (بدون ساعت) درست است",
    bot.format_persian_datetime("2026-09-21 12:00:00", with_time=False) == "1405/06/30",
)
check("زمان خالی به «نامشخص» تبدیل می‌شود", bot.format_persian_datetime(None) == "نامشخص")

# ---------------------------------------------------------------------------
# ۶) دکمه‌ها و صفحه‌های پنل ادمین
# ---------------------------------------------------------------------------
print("\n=== ۶) دکمه‌های جدید پنل مدیریت ===")

panel_buttons = [b.text for row in bot.admin_panel_kb().keyboard for b in row]
check("دکمه «کاربران ربات» در پنل مدیریت هست", bot.BTN_ADMIN_USERS_LOG.text in panel_buttons)
check(
    "دکمه «لاگ استفاده از ربات» در پنل مدیریت هست",
    bot.BTN_ADMIN_USAGE_LOG.text in panel_buttons,
)

users_page_text, users_page_kb = bot.build_users_log_page(0)
check("صفحه کاربران شامل تاریخ عضویت است", "عضویت در ربات" in users_page_text)
check("صفحه کاربران شامل آمار کل کاربران است", "کل کاربران" in users_page_text)
check("صفحه کاربران نام کاربر را نشان می‌دهد", "علی" in users_page_text)

usage_page_text, usage_page_kb = bot.build_usage_log_page(0)
check("صفحه لاگ شامل تاریخ عضویت کاربر است", "عضویت در ربات" in usage_page_text)
check("صفحه لاگ شامل عمل انجام‌شده است", "عمل انجام‌شده" in usage_page_text)
check("صفحه لاگ شامل استفاده امروز است", "استفاده امروز" in usage_page_text)

# ---------------------------------------------------------------------------
# ۷) دکمه‌های پنل برای ادمین/کارفرما کار می‌کنند
# ---------------------------------------------------------------------------
print("\n=== ۷) عملکرد دکمه‌های لاگ برای ادمین ===")


async def click_admin_button(user_id, button_text, user_data=None):
    user = FakeUser(user_id, first_name="مدیر")
    update = make_update(user, button_text)
    context = make_context(user_data)
    await bot.handle_all_messages(update, context)
    return update.message.reply_text


owner_reply = asyncio.run(click_admin_button(OWNER, bot.BTN_ADMIN_USERS_LOG.text))
check("ادمین با زدن دکمه کاربران، لیست کاربران را می‌بیند", owner_reply.await_count == 1)
owner_text = owner_reply.await_args[0][0]
check("لیست ارسالی به ادمین شامل تاریخ عضویت است", "عضویت در ربات" in owner_text)

usage_reply = asyncio.run(click_admin_button(OWNER, bot.BTN_ADMIN_USAGE_LOG.text))
check("ادمین با زدن دکمه لاگ، لاگ استفاده را می‌بیند", usage_reply.await_count == 1)
usage_text = usage_reply.await_args[0][0]
check(
    "لاگ ارسالی شامل «چه کسی و با چه تاریخ عضویتی» است",
    "عضویت در ربات" in usage_text and "عمل انجام‌شده" in usage_text,
)

# کاربر عادی نباید به لاگ دسترسی داشته باشد و فقط به عنوان استفاده ثبت می‌شود
regular_logs_before = db_module.get_usage_logs_count()
regular_reply = asyncio.run(click_admin_button(REGULAR_USER, bot.BTN_ADMIN_USERS_LOG.text))
check("کاربر عادی پاسخ لاگ کاربران را نمی‌گیرد", regular_reply.await_count == 0)
check(
    "فشردن دکمه توسط کاربر عادی فقط به عنوان استفاده ثبت شد",
    db_module.get_usage_logs_count() == regular_logs_before + 1,
)

# ---------------------------------------------------------------------------
# ۸) ثبت خودکار استفاده از ربات در سناریوی واقعی کاربر
# ---------------------------------------------------------------------------
print("\n=== ۸) ثبت خودکار استفاده از ربات (start و ثبت درخواست عکس) ===")

customer = FakeUser(CUSTOMER, first_name="علی", username="customer_new")
start_update = make_update(customer)
start_context = make_context({"branch": "mashhad"})
asyncio.run(bot.start(start_update, start_context))

usage_rows = db_module.get_usage_logs(limit=5)
check(
    "دستور /start در لاگ استفاده ثبت شد",
    usage_rows[0]["action"] == "شروع ربات (/start)",
    usage_rows[0]["action"],
)
check("لاگ /start تاریخ عضویت را هم دارد", bool(usage_rows[0]["joined_at"]))

menu_update = make_update(customer, "دریافت عکس یادگاری")
menu_context = make_context({"branch": "mashhad"})
asyncio.run(bot.handle_all_messages(menu_update, menu_context))
usage_rows = db_module.get_usage_logs(limit=5)
check(
    "فشردن دکمه «دریافت عکس یادگاری» در لاگ ثبت شد",
    usage_rows[0]["action"] == "دریافت عکس یادگاری",
    usage_rows[0]["action"],
)

phone_update = make_update(customer, "09121234567")
phone_context = make_context(
    {
        "branch": "mashhad",
        "photo_branch": "mashhad",
        "photo_step": "phone",
        "photo_code": "1234",
        "photo_date": "1404/01/01",
    }
)
asyncio.run(bot.handle_all_messages(phone_update, phone_context))

usage_rows = db_module.get_usage_logs(limit=3)
actions = [row["action"] for row in usage_rows]
check(
    "ورود شماره تلفن در لاگ ثبت شد",
    "ورود شماره تلفن: 09121234567" in actions,
    str(actions),
)
check(
    "ثبت درخواست عکس یادگاری در لاگ ثبت شد",
    "ثبت درخواست عکس یادگاری" in actions,
    str(actions),
)
photo_log = next(
    row for row in usage_rows if row["action"] == "ثبت درخواست عکس یادگاری"
)
check(
    "جزئیات درخواست (تلفن/کد/شعبه) در لاگ ثبت شد",
    "09121234567" in (photo_log["detail"] or "")
    and "1234" in (photo_log["detail"] or ""),
    str(photo_log["detail"]),
)
check("لاگ درخواست عکس تاریخ عضویت کاربر را نشان می‌دهد", bool(photo_log["joined_at"]))

# ---------------------------------------------------------------------------
# ۹) صفحه‌بندی لاگ‌ها
# ---------------------------------------------------------------------------
print("\n=== ۹) صفحه‌بندی لاگ کاربران ===")

for index in range(25):
    db_module.log_bot_usage(
        920000000 + index, "تست صفحه‌بندی", first_name=f"کاربر {index}"
    )

page_one_text, page_one_kb = bot.build_users_log_page(0)
page_one_buttons = [b.text for row in page_one_kb.inline_keyboard for b in row]
check("در صفحه اول دکمه «صفحه بعد» هست", "صفحه بعد ➡️" in page_one_buttons)

page_two_text, page_two_kb = bot.build_users_log_page(10)
page_two_buttons = [b.text for row in page_two_kb.inline_keyboard for b in row]
check(
    "در صفحه دوم دکمه «صفحه قبل» و «صفحه بعد» هست",
    "⬅️ صفحه قبل" in page_two_buttons and "صفحه بعد ➡️" in page_two_buttons,
)
check("صفحه دوم با صفحه اول تفاوت دارد", page_one_text != page_two_text)

clamped_text, _ = bot.build_users_log_page(9999)
check("شماره صفحه خارج از بازه به آخرین صفحه محدود می‌شود", "صفحه" in clamped_text)

check(
    "استخراج شماره صفحه از دکمه کار می‌کند",
    bot._parse_log_callback_offset("users_log:30") == 30,
)
check(
    "داده نامعتبر دکمه باعث خطا نمی‌شود",
    bot._parse_log_callback_offset("users_log") == 0,
)

# ---------------------------------------------------------------------------
# ۱۰) پاک‌سازی لاگ‌های قدیمی
# ---------------------------------------------------------------------------
print("\n=== ۱۰) پاک‌سازی لاگ‌های قدیمی ===")

conn = sqlite3.connect(TMP_DB)
conn.execute(
    """
    INSERT INTO usage_logs (user_id, action, created_at)
    VALUES (?, ?, datetime('now', '-400 days'))
""",
    (CUSTOMER, "لاگ قدیمی"),
)
conn.commit()
conn.close()

before_cleanup = db_module.get_usage_logs_count()
removed = db_module.delete_old_usage_logs(days=180)
check("لاگ قدیمی حذف شد", removed == 1, f"removed={removed}")
check(
    "تعداد لاگ‌ها بعد از پاک‌سازی درست است",
    db_module.get_usage_logs_count() == before_cleanup - 1,
)

# ---------------------------------------------------------------------------
# نتیجه نهایی
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(
    f"تعداد تست‌ها: {len(RESULTS)} | موفق: {sum(RESULTS)} | ناموفق: {len(RESULTS) - sum(RESULTS)}"
)
print("=" * 50)
