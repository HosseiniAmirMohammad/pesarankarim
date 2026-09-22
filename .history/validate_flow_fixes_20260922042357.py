import asyncio
import importlib.util
import os
import sqlite3
import tempfile
import types
from unittest.mock import AsyncMock

BASE = os.path.dirname(os.path.abspath(__file__))

# ===== دیتابیس تست (فایل موقت) =====
import database as db_module

TMP_DB = os.path.join(tempfile.gettempdir(), "pesarankarim_validate_flows.db")
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

ADMIN = bot.MAIN_ADMIN_ID
CUSTOMER = 902001001

RESULTS = []


def check(name, condition, extra=""):
    RESULTS.append(bool(condition))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  ->  {extra}" if extra else ""))


class FakeUser:
    def __init__(self, user_id, first_name="کاربر تست"):
        self.id = user_id
        self.first_name = first_name


class FakeMessage:
    def __init__(self, text=None, chat_id=1):
        self.text = text
        self.chat_id = chat_id
        self.message_id = 10
        self.animation = None
        self.video = None
        self.document = None
        self.photo = None
        self.caption = None
        self.reply_text = AsyncMock()


def make_update(user, text=None, chat_id=1, chat_type="private", message=None):
    return types.SimpleNamespace(
        effective_user=user,
        effective_chat=types.SimpleNamespace(type=chat_type, id=chat_id),
        message=message or FakeMessage(text, chat_id=chat_id),
        callback_query=None,
    )


def make_context(user_data=None):
    """context تست همراه با ثبت فراخوانی‌های ربات"""
    call_log = []
    bot_stub = types.SimpleNamespace(call_log=call_log)

    def recorder(name):
        stub = AsyncMock()

        async def _call(*args, **kwargs):
            call_log.append((name, kwargs))
            return None

        stub.side_effect = _call
        return stub

    bot_stub.send_message = recorder("send_message")
    bot_stub.send_animation = recorder("send_animation")
    bot_stub.copy_message = recorder("copy_message")

    return types.SimpleNamespace(
        user_data=user_data if user_data is not None else {}, bot=bot_stub
    )


def keyboard_texts(markup):
    """متن دکمه‌های یک ReplyKeyboard (اگر markup نبود None)"""
    if markup is None or not hasattr(markup, "keyboard"):
        return None
    return [button.text for row in markup.keyboard for button in row]


def inline_button_texts(markup):
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return []
    return [button.text for row in markup.inline_keyboard for button in row]


def inline_callback_data(markup):
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return []
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def inline_button_objs(markup):
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return []
    return [button for row in markup.inline_keyboard for button in row]


def sent_captions(context, chat_id):
    """کپشن فایل‌های ارسال‌شده برای یک چت"""
    return [
        kwargs.get("caption")
        for name, kwargs in context.bot.call_log
        if kwargs.get("chat_id") == chat_id
        and name in ("send_photo", "send_document", "send_animation", "send_video")
    ]


def messages_to(context, chat_id):
    return [
        kwargs.get("text")
        for name, kwargs in context.bot.call_log
        if name == "send_message" and kwargs.get("chat_id") == chat_id
    ]


def reply_markups_sent_to(context, chat_id):
    return [
        kwargs.get("reply_markup")
        for name, kwargs in context.bot.call_log
        if name == "send_message" and kwargs.get("chat_id") == chat_id
    ]


def reply_texts(update):
    return [call.args[0] for call in update.message.reply_text.await_args_list]


def reply_markups(update):
    return [
        call.kwargs.get("reply_markup")
        for call in update.message.reply_text.await_args_list
    ]


def db_rows(query, params=()):
    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


db_module.init_db()
db_module.init_admin_user()

# ===========================================================================
# ۱) گروه کاری عکس: دکمه «نه، تمام شد» کیبورد گیرکرده را پاک می‌کند
# ===========================================================================
print("=== ۱) گروه کاری عکس ===")

group_context = make_context(
    {
        "admin_upload": {
            "phone": "09123334455",
            "photo_code": "7788",
            "branch": "mashhad",
            "user_id": CUSTOMER,
            "count": 2,
            "step": "asking",
        }
    }
)
group_update = make_update(
    FakeUser(ADMIN, first_name="مدیر"),
    bot.BTN_NO.text,
    chat_id=bot.GROUP_MASHHAD_PHOTO,
    chat_type="supergroup",
    message=FakeMessage(bot.BTN_NO.text, chat_id=bot.GROUP_MASHHAD_PHOTO),
)
asyncio.run(bot.handle_photo_group_text(group_update, group_context))

check(
    "وضعیت آپلود ادمین در گروه بسته شد",
    group_context.user_data.get("admin_upload") is None,
)
check(
    "در گروه پیام پایان کار ارسال شد",
    any("همه عکس‌ها ارسال شدند" in t for t in reply_texts(group_update)),
)
check(
    "ReplyKeyboardRemove ارسال شد (کیبورد بله/خیر از صفحه پاک می‌شود)",
    any(isinstance(m, bot.ReplyKeyboardRemove) for m in reply_markups(group_update)),
)
check(
    "پنل مدیریت داخل گروه ارسال نشد",
    not any(
        keyboard_texts(m) and bot.BTN_ADMIN_MANAGE.text in keyboard_texts(m)
        for m in reply_markups(group_update)
    ),
)
check(
    "کپشن عکس‌های ارسالی (در صورت وجود) متن تحویل عکس است",
    not sent_captions(group_context, CUSTOMER)
    or all(
        c == bot.PHOTO_DELIVERED_MESSAGE for c in sent_captions(group_context, CUSTOMER)
    ),
)
check(
    "پیام تحویل عکس دیگر جداگانه ارسال نمی‌شود",
    bot.PHOTO_DELIVERED_MESSAGE not in messages_to(group_context, CUSTOMER),
)
check(
    "نظرسنجی مشتری شروع شد (پرسش ۵ ستاره)",
    bot.SURVEY_FIVE_STAR_QUESTION in messages_to(group_context, CUSTOMER),
)

other_update = make_update(
    FakeUser(ADMIN),
    "سلام",
    chat_id=bot.GROUP_MASHHAD_PHOTO,
    chat_type="supergroup",
    message=FakeMessage("سلام", chat_id=bot.GROUP_MASHHAD_PHOTO),
)
other_context = make_context(
    {
        "admin_upload": {
            "phone": "1",
            "photo_code": "2",
            "branch": "mashhad",
            "user_id": 5,
        }
    }
)
asyncio.run(bot.handle_photo_group_text(other_update, other_context))
check(
    "پیام‌های دیگر در گروه کاری بی‌پاسخ می‌مانند",
    other_update.message.reply_text.await_count == 0
    and other_context.bot.send_message.await_count == 0,
)

# ===========================================================================
# ۲) نظرسنجی خصوصی: بعد از «بله» کاربر به منوی اصلی برمی‌گردد
# ===========================================================================
print("\n=== ۲) نظرسنجی خصوصی: بازگشت به منو بعد از بله ===")

survey_context = make_context({"branch": "mashhad", "survey_step": "five_star"})
survey_update = make_update(
    FakeUser(CUSTOMER, first_name="مشتری"), bot.BTN_SURVEY_YES.text
)
asyncio.run(bot.handle_all_messages(survey_update, survey_context))

check(
    "وضعیت نظرسنجی بعد از بله پاک شد",
    survey_context.user_data.get("survey_step") is None,
)
check(
    "گیف نظرسنجی برای مشتری ارسال شد",
    any(
        name in ("send_animation", "copy_message")
        for name, _ in survey_context.bot.call_log
    ),
)
gif_call = [
    kw
    for name, kw in survey_context.bot.call_log
    if name in ("send_animation", "copy_message")
][0]
check(
    "دکمه «✅ نظر دادم» زیر گیف هست",
    inline_button_texts(gif_call.get("reply_markup")) == ["✅ نظر دادم"],
    str(inline_button_texts(gif_call.get("reply_markup"))),
)
check(
    "callback دکمه نظر دادم درست است",
    inline_callback_data(gif_call.get("reply_markup")) == ["claim_reward|mashhad"],
)
check(
    "پیام تشکر بدون دکمه ارسال می‌شود (دکمه لینک گوگل حذف شد)",
    all(
        kwargs.get("reply_markup") is None
        for name, kwargs in survey_context.bot.call_log
        if name == "send_message" and kwargs.get("text") == bot.GOOGLE_REVIEW_MESSAGE
    ),
)
check(
    "هیچ دکمه لینک گوگل در جریان نظرسنجی وجود ندارد",
    not any(
        b.url and "google" in (b.url or "").lower()
        for m in reply_markups_sent_to(survey_context, CUSTOMER)
        if m is not None
        for b in inline_button_objs(m)
    ),
)
check(
    "پیام دعوت به دریافت امتیاز جداگانه دیگر ارسال نمی‌شود",
    not any(
        "هدیه 10 امتیازی" in (t or "") for t in messages_to(survey_context, CUSTOMER)
    ),
)
check(
    "بعد از بله، منوی اصلی برای کاربر ارسال شد",
    any(
        isinstance(m, bot.ReplyKeyboardMarkup)
        and keyboard_texts(m)
        and "دریافت عکس یادگاری" in keyboard_texts(m)
        and "پشتیبانی" in keyboard_texts(m)
        for m in reply_markups_sent_to(survey_context, CUSTOMER)
    ),
)
check(
    "بعد از بله، کیبورد بله/خیر دیگر ارسال نمی‌شود",
    not any(
        keyboard_texts(m) == [bot.BTN_SURVEY_YES.text, bot.BTN_SURVEY_NO.text]
        for m in reply_markups_sent_to(survey_context, CUSTOMER)
    ),
)

# ===========================================================================
# ۳) دکمه «✅ نظر دادم»: تبریک + ۱۰ امتیاز + بازگشت به منوی اصلی
# ===========================================================================
print("\n=== ۳) دکمه نظر دادم ===")

claim_context = make_context()
claim_update = types.SimpleNamespace(
    effective_user=FakeUser(CUSTOMER, first_name="مشتری"),
    effective_chat=types.SimpleNamespace(type="private"),
    message=None,
    callback_query=types.SimpleNamespace(
        from_user=FakeUser(CUSTOMER),
        data="claim_reward|mashhad",
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    ),
)
asyncio.run(bot.claim_reward_callback(claim_update, claim_context))

claim_rows = db_rows("SELECT * FROM review_rewards WHERE user_id = ?", (CUSTOMER,))
check("ثبت امتیاز در دیتابیس", len(claim_rows) == 1)
check(
    "پیام تبریک و اعلام ۱۰ امتیاز برای کاربر ارسال شد",
    any(
        "تبریک" in (t or "") and "10 امتیاز" in (t or "")
        for t in messages_to(claim_context, CUSTOMER)
    ),
)
check(
    "بعد از دریافت امتیاز، منوی اصلی ارسال شد",
    any(
        isinstance(m, bot.ReplyKeyboardMarkup)
        and keyboard_texts(m)
        and "دریافت عکس یادگاری" in keyboard_texts(m)
        for m in reply_markups_sent_to(claim_context, CUSTOMER)
    ),
)

# ===========================================================================
# نتیجه نهایی
# ===========================================================================
print("\n" + "=" * 50)
print(
    f"تعداد تست‌ها: {len(RESULTS)} | موفق: {sum(RESULTS)} | ناموفق: {len(RESULTS) - sum(RESULTS)}"
)
print("=" * 50)
