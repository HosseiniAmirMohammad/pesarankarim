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

TMP_DB = os.path.join(tempfile.gettempdir(), "pesarankarim_validate_admin.db")
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
db_module.DB_PATH = TMP_DB

# ===== بارگذاری ماژول اصلی ربات =====
spec = importlib.util.spec_from_file_location(
    "pesarankarim_mod", os.path.join(BASE, "pesarankarim.py")
)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

OWNER = bot.OWNER_ID
MAIN_ADMIN = bot.MAIN_ADMIN_ID
CUSTOMER = 900907001
STAFF = 123456789

RESULTS = []


def check(name, condition, extra=""):
    RESULTS.append(bool(condition))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  ->  {extra}" if extra else ""))


def fetch_admins():
    conn = sqlite3.connect(TMP_DB)
    rows = conn.execute("SELECT user_id, is_active FROM admins").fetchall()
    conn.close()
    return dict(rows)


def fetch_preuploaded():
    conn = sqlite3.connect(TMP_DB)
    rows = conn.execute(
        "SELECT phone, photo_code, branch, file_id FROM preuploaded_photos"
    ).fetchall()
    conn.close()
    return rows


def fetch_request_status(phone, code, branch):
    conn = sqlite3.connect(TMP_DB)
    row = conn.execute(
        "SELECT status FROM photo_requests WHERE phone=? AND photo_code=? AND branch=?",
        (phone, code, branch),
    ).fetchone()
    conn.close()
    return row[0] if row else None
# ---------------------------------------------------------------------------
# ۱) دسترسی کامل کارفرما (سازنده ربات) به پنل ادمین
# ---------------------------------------------------------------------------
print("\n=== ۱) دسترسی سازنده/کارفرما به پنل مدیریت ===")

db_module.init_db()
admins_after_init = fetch_admins()
check(
    f"آیدی کارفرما ({OWNER}) به صورت خودکار در لیست ادمین‌ها ثبت شد",
    admins_after_init.get(OWNER) == 1,
    str(admins_after_init),
)
check("is_admin(کارفرما) = True", db_module.is_admin(OWNER) is True)
check("is_super_admin(کارفرما) = True", db_module.is_super_admin(OWNER) is True)
check("is_admin(مدیر اصلی) = True", db_module.is_admin(MAIN_ADMIN) is True)
check("is_admin(کاربر عادی) = False", db_module.is_admin(STAFF) is False)

# دکمه پنل مدیریت در منوی کارفرما دیده می‌شود
panel_text = bot.BTN_ADMIN_PANEL.text
owner_menu = bot.mashhad_menu_kb(OWNER)
owner_buttons = [b.text for row in owner_menu.keyboard for b in row]
check("دکمه «پنل مدیریت» در منوی کارفرما نمایش داده می‌شود", panel_text in owner_buttons)

staff_menu = bot.tehran_menu_kb(STAFF)
staff_buttons = [b.text for row in staff_menu.keyboard for b in row]
check(
    "دکمه «پنل مدیریت» برای کاربر عادی نمایش داده نمیشود",
    panel_text not in staff_buttons,
)

# سازنده/کارفرما قابل حذف شدن نیست
check("remove_admin(کارفرما) مسدود است", db_module.remove_admin(OWNER) is False)
check("کارفرما بعد از تلاش حذف، همچنان فعال است", fetch_admins().get(OWNER) == 1)
check(
    "delete_admin_permanently(کارفرما) مسدود است",
    db_module.delete_admin_permanently(OWNER) is False,
)
check("کارفرما بعد از حذف کامل، همچنان در دیتابیس است", fetch_admins().get(OWNER) == 1)
check("is_admin(کارفرما) همیشه True است", db_module.is_admin(OWNER) is True)

# مدیریت ادمین‌های عادی همچنان کار میکند
db_module.add_admin(555000111, "test_admin", "Test", None, OWNER)
check("افزودن ادمین عادی کار می‌کند", db_module.is_admin(555000111) is True)
check("حذف ادمین عادی کار می‌کند", db_module.remove_admin(555000111) is True)
check("ادمین عادی بعد از حذف غیرفعال است", db_module.is_admin(555000111) is False)

# ---------------------------------------------------------------------------
# ۲) ارسال عکس در گروه‌ها توسط همه اعضا (بدون پیام «دسترسی ندارید»)
# ---------------------------------------------------------------------------
print("\n=== ۲) ارسال عکس در گروه‌های عکس توسط اعضای عادی ===")


async def send_group_photo(
    sender_id,
    chat_id=None,
    caption=None,
    with_photo=True,
    file_id="FID-1",
    as_document=False,
    user_data=None,
    bot_module=None,
):
    """شبیه‌سازی ارسال عکس در گروه توسط یک کاربر تلگرام"""
    bot_module = bot_module or bot
    message = types.SimpleNamespace(
        chat_id=chat_id if chat_id is not None else bot_module.GROUP_MASHHAD_PHOTO,
        caption=caption,
        photo=(
            [types.SimpleNamespace(file_id=file_id)]
            if with_photo and not as_document
            else None
        ),
        document=(
            types.SimpleNamespace(file_id=file_id) if as_document else None
        ),
        message_id=42,
        reply_text=AsyncMock(),
    )
    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id=sender_id, first_name="Staff"),
        message=message,
        effective_chat=types.SimpleNamespace(type="supergroup"),
    )
    context = types.SimpleNamespace(
        user_data={} if user_data is None else user_data,
        bot=types.SimpleNamespace(
            send_photo=AsyncMock(),
            send_document=AsyncMock(),
            send_message=AsyncMock(),
        ),
    )
    await bot_module.handle_group_photo(update, context)
    return message, context


def replies_of(message):
    return [c.args[0] for c in message.reply_text.await_args_list if c.args]


def no_access_message(message):
    return any("دسترسی" in str(r) for r in replies_of(message))


# درخواست عکس در انتظار برای مشتری
db_module.save_photo_request(CUSTOMER, "09121112233", "4321", "1404/01/01", "mashhad")

# ۲-۱) عضو عادی گروه، عکس با کپشن صحیح می‌فرستد -> باید برای مشتری ارسال شود
message, context = asyncio.run(
    send_group_photo(STAFF, bot.GROUP_MASHHAD_PHOTO, "09121112233 4321")
)
check(
    "عضو عادی گروه پیام «دسترسی ندارید» نمی‌گیرد",
    not no_access_message(message),
    str(replies_of(message)),
)
check(
    "عکس عضو عادی برای مشتری ارسال شد",
    context.bot.send_photo.await_count == 1
    and context.bot.send_photo.await_args.kwargs.get("chat_id") == CUSTOMER,
    str(context.bot.send_photo.await_args.kwargs if context.bot.send_photo.await_args else {}),
)
check("تأییدیه ارسال برای فرستنده نمایش داده شد", any("✅" in str(r) for r in replies_of(message)))
check(
    "وضعیت درخواست مشتری به sent تغییر کرد",
    fetch_request_status("09121112233", "4321", "mashhad") == "sent",
    str(fetch_request_status("09121112233", "4321", "mashhad")),
)

# ۲-۲) عضو عادی بدون کپشن عکس می‌فرستد -> هیچ پیامی نباید بگیرد
message, context = asyncio.run(send_group_photo(STAFF, bot.GROUP_MASHHAD_PHOTO, None))
check("عکس بدون کپشن: هیچ پیامی برای عضو گروه ارسال نمی‌شود", message.reply_text.await_count == 0)
check("عکس بدون کپشن: فایلی برای مشتری ارسال نمی‌شود", context.bot.send_photo.await_count == 0)

# ۲-۳) عضو عادی گروه تهران، عکس با کپشن صحیح ولی بدون درخواست ثبت‌شده
message, context = asyncio.run(
    send_group_photo(STAFF, bot.GROUP_TEHRAN_PHOTO, "09355556666 9876", file_id="FID-2")
)
rows = fetch_preuploaded()
check(
    "عکس عضو عادی گروه تهران به عنوان پیش‌آپلود ذخیره شد",
    ("09355556666", "9876", "tehran", "FID-2") in rows,
    str(rows),
)
check("برای عکس تازه، تأییدیه ذخیره نمایش داده شد", any("✅" in str(r) for r in replies_of(message)))

# ۲-۴) فرستادن فایل (document) در گروه توسط عضو عادی
message, context = asyncio.run(
    send_group_photo(
        STAFF, bot.GROUP_MASHHAD_PHOTO, "09121112233 4321", as_document=True, file_id="FID-3"
    )
)
check(
    "ارسال فایل (document) توسط عضو عادی پردازش می‌شود",
    not no_access_message(message),
    str(replies_of(message)),
)

# ۲-۵) سازنده/کارفرما با فلوی پیش‌آپلود ادمین در گروه عکس می‌فرستد
message, context = asyncio.run(
    send_group_photo(
        OWNER,
        bot.GROUP_MASHHAD_PHOTO,
        None,
        file_id="FID-OWNER",
        user_data={
            "admin_action": "preupload_photo",
            "preupload_phone": "09120001111",
            "preupload_code": "5555",
        },
    )
)
rows = fetch_preuploaded()
check(
    "فلوی پیش‌آپلود ادمین همچنان کار می‌کند",
    ("09120001111", "5555", "mashhad", "FID-OWNER") in rows,
    str(rows),
)

# ---------------------------------------------------------------------------
# ۳) امکان محدود کردن دوباره گروه‌ها به ادمین‌ها (کلید config)
# ---------------------------------------------------------------------------
print("\n=== ۳) کلید ALLOW_GROUP_PHOTOS_FOR_ALL در config.py ===")

bot.ALLOW_GROUP_PHOTOS_FOR_ALL = False
message, context = asyncio.run(
    send_group_photo(STAFF, bot.GROUP_MASHHAD_PHOTO, "09121112233 4321")
)
check(
    "با False شدن کلید، عضو عادی پیام «دسترسی ندارید» می‌گیرد",
    no_access_message(message),
    str(replies_of(message)),
)

message, context = asyncio.run(
    send_group_photo(OWNER, bot.GROUP_MASHHAD_PHOTO, "09121112233 4321")
)
check(
    "حتی با False شدن کلید، کارفرما/ادمین مسدود نمی‌شود",
    not no_access_message(message),
    str(replies_of(message)),
)
bot.ALLOW_GROUP_PHOTOS_FOR_ALL = True

# ---------------------------------------------------------------------------
# ۴) پیام‌های متنی در گروه‌ها پردازش نمی‌شوند (فقط چت خصوصی)
# ---------------------------------------------------------------------------
print("\n=== ۴) فیلتر پیام متنی: فقط چت خصوصی ===")

from telegram import Update
from telegram.ext import filters

text_filter = filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE


def build_update(chat_type, text):
    return Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": -1001234567890 if chat_type != "private" else 555, "type": chat_type},
                "from": {"id": STAFF, "is_bot": False, "first_name": "Staff"},
                "text": text,
            },
        },
        bot=None,
    )


group_match = text_filter.check_update(build_update("supergroup", "سلام"))
private_match = text_filter.check_update(build_update("private", "سلام"))
check("پیام متنی گروه توسط فیلتر رد می‌شود", not group_match, str(group_match))
check("پیام متنی چت خصوصی توسط فیلتر قبول می‌شود", bool(private_match), str(private_match))

# ---------------------------------------------------------------------------
# ۵) بررسی ثبت هندلرها در main() (بدون اتصال به تلگرام)
# ---------------------------------------------------------------------------
print("\n=== ۵) پیکربندی هندلرها در main() ===")

from telegram.ext import Application, ApplicationBuilder

captured_app = {}


class SpyApplicationBuilder(ApplicationBuilder):
    def build(self):
        app = super().build()
        captured_app["app"] = app
        return app


real_builder_descriptor = Application.__dict__["builder"]
real_run_polling = Application.__dict__["run_polling"]

Application.builder = staticmethod(lambda: SpyApplicationBuilder())
Application.run_polling = lambda self, *args, **kwargs: None

try:
    bot.main()
finally:
    Application.builder = real_builder_descriptor
    Application.run_polling = real_run_polling

app = captured_app.get("app")
check("main() بدون خطا اجرا و اپلیکیشن ساخته شد", app is not None)

handlers = app.handlers[0] if app else []
text_handler = next(
    (h for h in handlers if getattr(h, "callback", None) is bot.handle_all_messages), None
)
check("هندلر پیام متنی ثبت شده است", text_handler is not None)
check(
    "هندلر پیام متنی، پیام گروه را رد می‌کند",
    not text_handler.filters.check_update(build_update("supergroup", "سلام")),
)
check(
    "هندلر پیام متنی، پیام چت خصوصی را قبول می‌کند",
    bool(text_handler.filters.check_update(build_update("private", "سلام"))),
)

photo_handlers = [
    h for h in handlers if getattr(h, "callback", None) is bot.handle_group_photo
]
check("هندلر عکس برای هر دو گروه (مشهد و تهران) ثبت شده است", len(photo_handlers) == 2)


def build_photo_update(chat_id, chat_type="supergroup"):
    return Update.de_json(
        {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "date": 0,
                "chat": {"id": chat_id, "type": chat_type},
                "from": {"id": STAFF, "is_bot": False, "first_name": "Staff"},
                "photo": [
                    {
                        "file_id": "FID-X",
                        "file_unique_id": "UQ-X",
                        "width": 100,
                        "height": 100,
                    }
                ],
            },
        },
        bot=None,
    )


matched_groups = [
    h.filters.check_update(build_photo_update(bot.GROUP_MASHHAD_PHOTO))
    for h in photo_handlers
]
check(
    "عکس ارسالی در گروه مشهد توسط هندلر گروه‌ها گرفته می‌شود",
    any(matched_groups),
    str(matched_groups),
)
check(
    "عکس ارسالی در چت خصوصی توسط هندلر گروه‌ها گرفته نمی‌شود",
    not any(
        h.filters.check_update(build_photo_update(STAFF, chat_type="private"))
        for h in photo_handlers
    ),
)

# ---------------------------------------------------------------------------
# ۶) نمایش دکمه «پنل مدیریت» در همه منوها برای ادمین‌ها (آیدی 383415679 و کارفرما)
# ---------------------------------------------------------------------------
print("\n=== ۶) دکمه پنل مدیریت در منوها ===")

bot.real_member = AsyncMock(return_value=True)
PANEL = bot.BTN_ADMIN_PANEL.text
MY_ID = bot.MAIN_ADMIN_ID


def buttons_of(markup):
    return [b.text for row in markup.keyboard for b in row]


def has_panel(markup):
    return markup is not None and PANEL in buttons_of(markup)


def last_markup(message):
    return message.reply_text.await_args_list[-1].kwargs.get("reply_markup")


async def send_text(sender_id, text, user_data=None):
    """شبیه‌سازی ارسال یک پیام متنی توسط کاربر در چت خصوصی"""
    message = types.SimpleNamespace(
        chat_id=sender_id,
        text=text,
        message_id=7,
        photo=None,
        document=None,
        caption=None,
        reply_text=AsyncMock(),
    )
    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id=sender_id, first_name="U"),
        message=message,
        effective_chat=types.SimpleNamespace(type="private"),
    )
    context = types.SimpleNamespace(
        user_data={} if user_data is None else user_data,
        bot=types.SimpleNamespace(
            send_message=AsyncMock(),
            send_photo=AsyncMock(),
            send_document=AsyncMock(),
            delete_message=AsyncMock(),
        ),
    )
    await bot.handle_all_messages(update, context)
    return message


check(
    "branch_menu_kb(مشهد) برای آیدی من دکمه پنل را دارد",
    has_panel(bot.branch_menu_kb("mashhad", MY_ID)),
)
check(
    "branch_menu_kb(تهران) برای آیدی من دکمه پنل را دارد",
    has_panel(bot.branch_menu_kb("tehran", MY_ID)),
)
check(
    "branch_menu_kb(مشهد) برای کارفرما دکمه پنل را دارد",
    has_panel(bot.branch_menu_kb("mashhad", OWNER)),
)
check(
    "branch_menu_kb(مشهد) برای کاربر عادی دکمه پنل را ندارد",
    not has_panel(bot.branch_menu_kb("mashhad", STAFF)),
)

msg = asyncio.run(send_text(MY_ID, "شعبه مشهد(خیام)"))
check("انتخاب شعبه مشهد توسط آیدی من: دکمه پنل نمایش داده می‌شود", has_panel(last_markup(msg)))

msg = asyncio.run(send_text(OWNER, "شعبه تهران(هتل پارسیان آزادی)"))
check("انتخاب شعبه تهران توسط کارفرما: دکمه پنل نمایش داده می‌شود", has_panel(last_markup(msg)))

msg = asyncio.run(send_text(STAFF, "شعبه مشهد(خیام)"))
check("انتخاب شعبه توسط کاربر عادی: دکمه پنل نمایش داده نمی‌شود", not has_panel(last_markup(msg)))

msg = asyncio.run(send_text(MY_ID, "🔙 بازگشت به منو", user_data={"branch": "tehran"}))
check(
    "بازگشت از پنل مدیریت به منو (آیدی من): دکمه پنل باقی می‌ماند",
    has_panel(last_markup(msg)),
    str(buttons_of(last_markup(msg))),
)

msg = asyncio.run(send_text(OWNER, bot.BTN_BACK_TEXT, user_data={"branch": "mashhad"}))
check(
    "دکمه «بازگشت» (کارفرما): دکمه پنل نمایش داده می‌شود",
    has_panel(last_markup(msg)),
    str(buttons_of(last_markup(msg))),
)

msg = asyncio.run(send_text(STAFF, bot.BTN_BACK_TEXT, user_data={"branch": "mashhad"}))
check(
    "دکمه «بازگشت» (کاربر عادی): دکمه پنل نمایش داده نمی‌شود",
    not has_panel(last_markup(msg)),
)

# ---------------------------------------------------------------------------
# خلاصه
# ---------------------------------------------------------------------------
print("\n=== خلاصه نتایج ===")
passed = sum(1 for r in RESULTS if r)
print(f"موفق: {passed} از {len(RESULTS)}")

if passed != len(RESULTS):
    print("❌ برخی بررسی‌ها ناموفق بودند.")
    raise SystemExit(1)

print("✅ همه بررسی‌ها با موفقیت انجام شد.")
print(f"(دیتابیس تست: {TMP_DB})")