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

TMP_DB = os.path.join(tempfile.gettempdir(), "pesarankarim_validate_waiting.db")
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

CUSTOMER = 900808001
SECOND_CUSTOMER = 900808002
REGULAR_USER = 900808003
OWNER = bot.OWNER_ID

MASHHAD_GROUP = bot.waiting_group_chat_id("mashhad")
TEHRAN_GROUP = bot.waiting_group_chat_id("tehran")

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
        self.message_id = 10


class FakeUser:
    def __init__(self, user_id, first_name="کاربر تست", username=None):
        self.id = user_id
        self.first_name = first_name
        self.last_name = None
        self.username = username


def make_update(user, text=None):
    return types.SimpleNamespace(
        effective_user=user, message=FakeMessage(text), callback_query=None
    )


def make_context(user_data=None, bot_has_send_photo=True):
    bot_stub = types.SimpleNamespace(
        send_message=AsyncMock(),
        send_photo=AsyncMock(),
        send_document=AsyncMock(),
        delete_message=AsyncMock(),
        get_chat_member=AsyncMock(),
    )
    return types.SimpleNamespace(
        user_data=user_data if user_data is not None else {}, bot=bot_stub
    )


def group_messages(context, chat_id):
    """پیام‌هایی که بات به گروه مشخص ارسال کرده است"""
    return [
        call.kwargs["text"]
        for call in context.bot.send_message.await_args_list
        if call.kwargs.get("chat_id") == chat_id
    ]


def fetch_pending(branch):
    conn = sqlite3.connect(TMP_DB)
    rows = conn.execute(
        "SELECT phone FROM photo_requests WHERE status = 'pending' AND branch = ?",
        (branch,),
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def request_row(phone):
    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM photo_requests WHERE phone = ? ORDER BY id DESC LIMIT 1", (phone,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


print("\n=== ۱) آیدی گروه‌های لیست انتظار ===")
db_module.init_db()
db_module.init_admin_user()

check(
    "آیدی گروه مشهد درست است",
    MASHHAD_GROUP == -1004355675580,
    str(MASHHAD_GROUP),
)
check(
    "آیدی گروه تهران درست است",
    TEHRAN_GROUP == -1004473279586,
    str(TEHRAN_GROUP),
)
check(
    "آیدی بدون منفی به‌صورت خودکار اصلاح می‌شود",
    bot.normalize_group_chat_id(1004473279586) == -1004473279586,
)
check(
    "آیدی منفی دست‌نخورده می‌ماند",
    bot.normalize_group_chat_id(-1004473279586) == -1004473279586,
)
check("آیدی نامعتبر باعث خطا نمی‌شود", bot.normalize_group_chat_id("گروه تست") is None)
check(
    "فاصله ارسال دوره‌ای از config خوانده می‌شود",
    bot.WAITING_LIST_INTERVAL_HOURS == 3,
    str(bot.WAITING_LIST_INTERVAL_HOURS),
)

# ---------------------------------------------------------------------------
# ۲) اطلاع‌رسانی درخواست جدید در گروه لیست انتظار
# ---------------------------------------------------------------------------
print("\n=== ۲) اطلاع‌رسانی درخواست جدید در گروه لیست انتظار ===")

customer = FakeUser(CUSTOMER, first_name="علی", username="ali_test")

context = make_context(
    {
        "branch": "mashhad",
        "photo_branch": "mashhad",
        "photo_step": "phone",
        "photo_code": "1234",
        "photo_date": "1404/01/01",
    }
)
asyncio.run(
    bot.handle_all_messages(make_update(customer, "09121234567"), context)
)

mashhad_messages = group_messages(context, MASHHAD_GROUP)
check("درخواست جدید در گروه لیست انتظار مشهد اطلاع داده شد", len(mashhad_messages) == 1)
check("به گروه لیست انتظار تهران پیامی ارسال نشد", not group_messages(context, TEHRAN_GROUP))
new_request_text = mashhad_messages[0] if mashhad_messages else ""
check("نام کاربر در پیام گروه آمده است", "علی" in new_request_text, new_request_text)
check("یوزرنیم کاربر در پیام گروه آمده است", "@ali_test" in new_request_text)
check("آیدی عددی کاربر در پیام گروه آمده است", str(CUSTOMER) in new_request_text)
check("تاریخ عضویت کاربر در پیام گروه آمده است", "عضویت در ربات:" in new_request_text)
check("شماره تلفن در پیام گروه آمده است", "09121234567" in new_request_text)
check("کد عکس در پیام گروه آمده است", "1234" in new_request_text)
check("تاریخ عکس در پیام گروه آمده است", "1404/01/01" in new_request_text)
check("از تیم خواسته شده عکس را ارسال کنند", "عکس این کاربر ارسال شود" in new_request_text)
check("شعبه در پیام گروه مشخص است", "مشهد" in new_request_text)

check(
    "درخواست در دیتابیس ثبت شد",
    request_row("09121234567") is not None,
)
check(
    "وضعیت درخواست در انتظار است",
    request_row("09121234567")["status"] == "pending",
)

# درخواست شعبه تهران به گروه تهران می‌رود
tehran_context = make_context(
    {
        "branch": "tehran",
        "photo_branch": "tehran",
        "photo_step": "phone",
        "photo_code": "5678",
        "photo_date": "1404/02/02",
    }
)
asyncio.run(
    bot.handle_all_messages(
        make_update(FakeUser(SECOND_CUSTOMER, first_name="مریم"), "09129998877"),
        tehran_context,
    )
)
tehran_messages = group_messages(tehran_context, TEHRAN_GROUP)
check("درخواست شعبه تهران در گروه تهران ارسال شد", len(tehran_messages) == 1)
check("به گروه مشهد پیامی ارسال نشد", not group_messages(tehran_context, MASHHAD_GROUP))
check(
    "پیام گروه تهران شامل شماره و کد درست است",
    ("09129998877" in tehran_messages[0]) and ("5678" in tehran_messages[0]),
)

# ---------------------------------------------------------------------------
# ۳) عکس پیش‌آپلود: درخواست ارسال‌شده در لیست انتظار نمی‌آید
# ---------------------------------------------------------------------------
print("\n=== ۳) عکس پیش‌آپلود (ارسال خودکار) ===")

bot.get_preuploaded_photo = lambda *args, **kwargs: (
    77,
    "FILE_ID_TEST",
    "photo",
    12,
    "2026-09-21 08:00:00",
)
bot.mark_preuploaded_as_used = lambda *args, **kwargs: True
bot.send_preuploaded_file = AsyncMock(return_value=True)

preupload_context = make_context(
    {
        "branch": "mashhad",
        "photo_branch": "mashhad",
        "photo_step": "phone",
        "photo_code": "9999",
        "photo_date": "1403/12/29",
    }
)
preupload_user = FakeUser(900808004, first_name="سارا")
asyncio.run(
    bot.handle_all_messages(make_update(preupload_user, "09191112233"), preupload_context)
)

preupload_row = request_row("09191112233")
check("درخواست با عکس پیش‌آپلود ثبت شد", preupload_row is not None)
check(
    "وضعیت درخواست ارسال‌شده (sent) است",
    preupload_row["status"] == "sent",
    str(preupload_row),
)
check("زمان ارسال (sent_at) ثبت شد", bool(preupload_row["sent_at"]))
check(
    "درخواست ارسال‌شده در لیست انتظار مشهد نیست",
    "09191112233" not in fetch_pending("mashhad"),
)
preupload_messages = group_messages(preupload_context, MASHHAD_GROUP)
check(
    "در گروه لیست انتظار گفته شده عکس خودکار ارسال شد",
    any("به‌صورت خودکار" in text for text in preupload_messages),
    str(preupload_messages[-1:]),
)

# ---------------------------------------------------------------------------
# ۴) متن لیست انتظار
# ---------------------------------------------------------------------------
print("\n=== ۴) متن لیست کاربران در انتظار دریافت عکس ===")

bot.get_preuploaded_photo = lambda *args, **kwargs: None

mashhad_waiting_text = bot.waiting_list_text("mashhad")
check("متن لیست انتظار مشهد ساخته شد", bool(mashhad_waiting_text))
check(
    "عنوان لیست شامل نام شعبه است",
    "شعبه مشهد" in mashhad_waiting_text,
    mashhad_waiting_text.split("\n")[0],
)
check("تعداد افراد در انتظار در لیست آمده است", "تعداد در انتظار" in mashhad_waiting_text)
check("شماره کاربر در لیست آمده است", "09121234567" in mashhad_waiting_text)
check("کد عکس در لیست آمده است", "1234" in mashhad_waiting_text)
check("تاریخ عضویت کاربر در لیست آمده است", "عضویت در ربات:" in mashhad_waiting_text)
check("مدت انتظار در لیست آمده است", "در انتظار:" in mashhad_waiting_text)
check(
    "کاربری که عکسش ارسال شده در لیست نیست",
    "09191112233" not in mashhad_waiting_text,
)
check(
    "فاصله ارسال دوره‌ای در متن لیست آمده است",
    "3 ساعت یک‌بار" in mashhad_waiting_text,
)

tehran_waiting_text = bot.waiting_list_text("tehran")
check("لیست انتظار تهران شامل کاربر تهران است", "09129998877" in tehran_waiting_text)
check("لیست تهران کاربر مشهد را نشان نمی‌دهد", "09121234567" not in tehran_waiting_text)

# ---------------------------------------------------------------------------
# ۵) ارسال لیست به گروه
# ---------------------------------------------------------------------------
print("\n=== ۵) ارسال لیست انتظار به گروه‌ها ===")

send_context = make_context()
sent_ok = asyncio.run(bot.send_waiting_list_to_group(send_context.bot, "mashhad"))
check("لیست انتظار مشهد ارسال شد", sent_ok is True)
check(
    "لیست به آیدی درست گروه مشهد ارسال شد",
    len(group_messages(send_context, MASHHAD_GROUP)) == 1,
)
check(
    "به گروه تهران در این مرحله پیامی ارسال نشد",
    not group_messages(send_context, TEHRAN_GROUP),
)

# ---------------------------------------------------------------------------
# ۶) حذف از لیست انتظار بعد از ارسال عکس
# ---------------------------------------------------------------------------
print("\n=== ۶) حذف درخواست از لیست بعد از ارسال عکس ===")

check("قبل از ارسال، درخواست در لیست است", "09121234567" in fetch_pending("mashhad"))

updated = db_module.mark_request_as_sent("09121234567", "1234", "mashhad")
check("وضعیت درخواست به ارسال‌شده تغییر کرد", updated == 1, f"updated={updated}")
check(
    "درخواست از لیست انتظار حذف شد",
    "09121234567" not in fetch_pending("mashhad"),
)
check(
    "علامت‌گذاری دوباره روی درخواست ارسال‌شده اثری ندارد",
    db_module.mark_request_as_sent("09121234567", "1234", "mashhad") == 0,
)
check("زمان ارسال در دیتابیس ثبت شد", bool(request_row("09121234567")["sent_at"]))

empty_text = bot.waiting_list_text("mashhad")
check("بعد از ارسال همه عکس‌ها لیست مشهد خالی است", empty_text is None)
check(
    "ارسال لیست خالی به گروه انجام نمی‌شود",
    asyncio.run(bot.send_waiting_list_to_group(make_context().bot, "mashhad")) is False,
)

# ---------------------------------------------------------------------------
# ۷) شکستن پیام‌های طولانی
# ---------------------------------------------------------------------------
print("\n=== ۷) شکستن پیام‌های طولانی ===")

short_text = "خط اول\nخط دوم"
check("متن کوتاه یک پیام می‌ماند", bot.split_message_text(short_text) == [short_text])

long_text = "\n".join(f"خط شماره {index} " + "x" * 40 for index in range(300))
long_chunks = bot.split_message_text(long_text)
check("متن بلند به چند پیام شکسته می‌شود", len(long_chunks) > 1, f"chunks={len(long_chunks)}")
check("طول هر بخش مجاز است", all(len(chunk) <= 3900 for chunk in long_chunks))
check("محتوای متن حفظ می‌شود", "".join(long_chunks).count("خط شماره") == 300)

# ---------------------------------------------------------------------------
# ۸) زمان‌بند ارسال دوره‌ای
# ---------------------------------------------------------------------------
print("\n=== ۸) زمان‌بند ارسال دوره‌ای لیست انتظار ===")

scheduler_calls = []
original_send = bot.send_waiting_list_to_group
original_sleep = bot.asyncio.sleep


async def run_scheduler_once(send_side_effect):
    """زمان‌بند را فقط برای یک دور اجرا می‌کند (بعد از اولین وقفه، متوقف می‌شود)"""
    bot.send_waiting_list_to_group = AsyncMock(side_effect=send_side_effect)
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) > 1:
            raise asyncio.CancelledError()

    bot.asyncio.sleep = fake_sleep
    try:
        await bot.waiting_list_scheduler(types.SimpleNamespace(bot="BOT"))
    except asyncio.CancelledError:
        pass
    finally:
        bot.asyncio.sleep = original_sleep
    return sleep_calls


def record_branch(_bot, branch):
    scheduler_calls.append(branch)


sleep_calls = asyncio.run(run_scheduler_once(record_branch))
bot.send_waiting_list_to_group = original_send

check(
    "زمان‌بند به اندازه فاصله تنظیم‌شده صبر می‌کند",
    sleep_calls and sleep_calls[0] == 3 * 3600,
    str(sleep_calls),
)
check(
    "لیست هر دو شعبه در هر دور ارسال می‌شود",
    scheduler_calls == ["mashhad", "tehran"],
    str(scheduler_calls),
)

# خطا در یک شعبه نباید زمان‌بند را متوقف کند
scheduler_calls.clear()


def flaky_branch(_bot, branch):
    if branch == "mashhad":
        raise RuntimeError("خطای تستی")
    scheduler_calls.append(branch)


asyncio.run(run_scheduler_once(flaky_branch))
bot.send_waiting_list_to_group = original_send
check(
    "خطای یک شعبه مانع ارسال شعبه دیگر نمی‌شود",
    scheduler_calls == ["tehran"],
    str(scheduler_calls),
)

# ---------------------------------------------------------------------------
# ۹) دکمه ارسال دستی لیست انتظار در پنل مدیریت
# ---------------------------------------------------------------------------
print("\n=== ۹) دکمه ارسال دستی لیست انتظار در پنل مدیریت ===")

panel_buttons = [b.text for row in bot.admin_panel_kb().keyboard for b in row]
check(
    "دکمه «ارسال لیست انتظار» در پنل مدیریت هست",
    bot.BTN_ADMIN_SEND_WAITING_LIST.text in panel_buttons,
)

# یک درخواست جدید ثبت می‌کنیم تا لیست خالی نباشد
new_request_context = make_context(
    {
        "branch": "mashhad",
        "photo_branch": "mashhad",
        "photo_step": "phone",
        "photo_code": "4321",
        "photo_date": "1404/03/03",
    }
)
asyncio.run(
    bot.handle_all_messages(
        make_update(FakeUser(900808005, first_name="حسن"), "09123334455"),
        new_request_context,
    )
)

owner_update = make_update(FakeUser(OWNER, first_name="مدیر"), bot.BTN_ADMIN_SEND_WAITING_LIST.text)
owner_context = make_context()
asyncio.run(bot.handle_all_messages(owner_update, owner_context))

owner_group_messages = group_messages(owner_context, MASHHAD_GROUP)
check("با دکمه ادمین، لیست انتظار به گروه مشهد ارسال شد", len(owner_group_messages) == 1)
check(
    "لیست ارسالی شامل کاربر در انتظار است",
    owner_group_messages and "09123334455" in owner_group_messages[0],
)
check(
    "گزارش وضعیت ارسال برای ادمین آمده است",
    owner_update.message.reply_text.await_count == 1
    and "لیست" in owner_update.message.reply_text.await_args[0][0],
)

regular_update = make_update(FakeUser(REGULAR_USER), bot.BTN_ADMIN_SEND_WAITING_LIST.text)
regular_context = make_context()
asyncio.run(bot.handle_all_messages(regular_update, regular_context))
check(
    "کاربر عادی نمی‌تواند لیست انتظار را ارسال کند",
    regular_update.message.reply_text.await_count == 0
    and regular_context.bot.send_message.await_count == 0,
)

# ---------------------------------------------------------------------------
# نتیجه نهایی
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(
    f"تعداد تست‌ها: {len(RESULTS)} | موفق: {sum(RESULTS)} | ناموفق: {len(RESULTS) - sum(RESULTS)}"
)
print("=" * 50)
