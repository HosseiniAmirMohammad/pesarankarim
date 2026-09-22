from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from database import (
    save_photo_request,
    is_admin,
    is_super_admin,
    get_pending_requests,
    get_failed_requests,
    get_daily_stats,
    get_db_connection,
    get_all_admins,
    add_admin,
    remove_admin,
    save_preuploaded_photo,
    get_preuploaded_photo,
    mark_preuploaded_as_used,
    get_all_preuploaded_photos,
    init_db,
    init_admin_user,
    log_bot_usage,
    get_users_log,
    get_users_count,
    get_users_stats,
    get_usage_logs,
    get_usage_logs_count,
    get_user_record,
    get_pending_requests_with_users,
    mark_request_as_sent,
    update_survey_comment,
    get_last_request_phone,
    save_review_reward,
    get_review_rewards,
    get_review_rewards_count,
    get_review_rewards_stats,
    save_review_gif,
    get_review_gif,
    clear_review_gif,
)
import asyncio
import jdatetime
import re
import traceback
from datetime import datetime, timedelta, timezone
from config import *


# ===== نشان (NSHN) offer settings =====
NSHN_MASHHAD = "https://nshn.ir/b7_b1iYzQJjehk"
NSHN_TEHRAN = "https://nshn.ir/51_bvvEZexOWCR"
NSHN_REWARD_POINTS = 50
NSHN_BUTTON_TEXT = "✅ نظر دادم نشان"


def make_keyboard(buttons, row_width=2):
    return InlineKeyboardMarkup(
        [buttons[i : i + row_width] for i in range(0, len(buttons), row_width)]
    )


def persian_to_english_numbers(text):
    if text is None:
        return ""
    persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
    english_numbers = "0123456789"
    translation_table = str.maketrans(persian_numbers, english_numbers)
    return str(text).translate(translation_table)


def normalize_phone_number(phone):
    if phone is None:
        return ""
    clean = persian_to_english_numbers(phone)
    clean = re.sub(r"\D", "", clean)

    if clean.startswith("98") and len(clean) == 12:
        clean = "0" + clean[2:]
    elif clean.startswith("9") and len(clean) == 10:
        clean = "0" + clean
    elif clean.startswith("0") and len(clean) > 11:
        clean = clean[:11]

    return clean


def is_valid_phone_number(phone):
    normalized = normalize_phone_number(phone)
    if not normalized or not normalized.isdigit():
        return False
    if len(normalized) == 11 and normalized.startswith("09"):
        return True
    if len(normalized) == 10 and normalized.startswith("9"):
        return True
    return False


def normalize_photo_code(code):
    if code is None:
        return ""
    clean = persian_to_english_numbers(code)
    clean = re.sub(r"\D", "", clean)
    return clean


def extract_phone_and_code(raw_text):
    if raw_text is None:
        return "", ""

    text = str(raw_text).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if len(lines) >= 2:
        first = normalize_phone_number(lines[0])
        second = normalize_photo_code(lines[1])
        if first and second:
            return first, second

    parts = re.split(r"[\s,|]+", text)
    candidates = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        number = normalize_phone_number(cleaned)
        code = normalize_photo_code(cleaned)
        if number and len(number) in (10, 11, 12):
            candidates.append(("phone", number))
        if code and len(code) == 4:
            candidates.append(("code", code))

    phone = ""
    code = ""
    for kind, value in candidates:
        if kind == "phone" and len(value) == 11 and value.startswith("09"):
            phone = value
        elif kind == "code" and len(value) == 4:
            code = value

    if phone and code:
        return phone, code

    if text:
        phone_match = re.search(
            r"(?:\+?98|0)[\d۰۱۲۳۴۵۶۷۸۹]{9,11}", persian_to_english_numbers(text)
        )
        if phone_match:
            phone = normalize_phone_number(phone_match.group(0))
        code_match = re.search(r"\b\d{4}\b|\b[۰۱۲۳۴۵۶۷۸۹]{4}\b", text)
        if code_match:
            code = normalize_photo_code(code_match.group(0))

    return phone, code


# ===== ابزارهای لاگ کاربران ربات =====
IRAN_TIMEZONE = timezone(timedelta(hours=3, minutes=30))
USERS_LOG_PAGE_SIZE = 10
USAGE_LOG_PAGE_SIZE = 10
REWARD_CLAIMS_PAGE_SIZE = 10

# برچسب خوانا برای ورودی‌های وسط فرایند ثبت عکس
STEP_USAGE_LABELS = {
    "year": "انتخاب سال عکس",
    "month": "انتخاب ماه عکس",
    "day": "انتخاب روز عکس",
    "code": "ورود کد عکس",
    "phone": "ورود شماره تلفن",
}


def to_iran_datetime(sqlite_timestamp):
    """تبدیل زمان UTC ذخیره‌شده در دیتابیس به وقت ایران (UTC+3:30)"""
    if not sqlite_timestamp:
        return None

    text = str(sqlite_timestamp).strip()
    parsed = None
    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(text, date_format)
            break
        except ValueError:
            continue

    if parsed is None:
        return None

    return parsed.replace(tzinfo=timezone.utc).astimezone(IRAN_TIMEZONE)


def iran_now():
    """زمان فعلی به وقت ایران برای نشان دادن تاریخ/ساعت و محاسبه اختلاف زمان"""
    return datetime.now(IRAN_TIMEZONE)


def format_persian_datetime(sqlite_timestamp, with_time=True):
    """نمایش زمان دیتابیس به صورت تاریخ شمسی و ساعت به وقت ایران"""
    dt = to_iran_datetime(sqlite_timestamp)
    if dt is None:
        return "نامشخص"

    try:
        jalali_date = jdatetime.date.fromgregorian(date=dt.date()).strftime("%Y/%m/%d")
    except Exception:
        return "نامشخص"

    if not with_time:
        return jalali_date
    return f"{jalali_date} - {dt.strftime('%H:%M')}"


def format_user_display(user_id, first_name=None, username=None):
    """نمایش خوانا از کاربر برای لاگ‌ها"""
    name = (first_name or "").strip() or "کاربر بدون نام"
    if len(name) > 30:
        name = name[:30] + "…"

    parts = [name]
    if username:
        parts.append(f"@{username}")
    parts.append(f"آیدی: {user_id}")
    return " | ".join(parts)


def build_usage_action(text, step=None):
    """ساخت برچسب خوانا برای هر استفاده از ربات"""
    clean = re.sub(r"\s+", " ", text or "").strip()

    if step in STEP_USAGE_LABELS:
        return f"{STEP_USAGE_LABELS[step]}: {clean[:30]}"

    if len(clean) > 60:
        clean = clean[:60] + "…"
    return clean or "پیام بدون متن"


def log_user_activity(user, action, detail=None):
    """ثبت استفاده کاربر از ربات (کاربر در اولین استفاده به عنوان عضو ربات ثبت می‌شود)"""
    try:
        log_bot_usage(
            user_id=user.id,
            action=action,
            detail=detail,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
        )
    except Exception as e:
        print(f"❌ خطا در ثبت فعالیت کاربر: {e}")


def log_photo_request_activity(user, phone, photo_code, branch):
    """ثبت لاگ ثبت درخواست عکس یادگاری توسط کاربر"""
    branch_name = "مشهد" if branch == "mashhad" else "تهران"
    log_user_activity(
        user,
        "ثبت درخواست عکس یادگاری",
        detail=f"تلفن: {phone} | کد: {photo_code} | شعبه: {branch_name}",
    )


# ===== گروه‌های لیست انتظار دریافت عکس =====
def normalize_group_chat_id(chat_id):
    """اصلاح آیدی گروه/کانال تلگرام

    آیدی سوپرگروه‌ها در تلگرام با -100 شروع می‌شود؛ اگر آیدی بدون منفی وارد
    شده باشد (مثل 1004355675580)، همین تابع آن را اصلاح می‌کند.
    """
    try:
        value = int(str(chat_id).strip())
    except (TypeError, ValueError):
        return None

    if value <= 0:
        return value

    text = str(value)
    if not text.startswith("100"):
        text = "100" + text
    return int("-" + text)


def waiting_group_chat_id(branch):
    """آیدی گروه لیست انتظار هر شعبه"""
    chat_id = GROUP_TEHRAN_WAITING if branch == "tehran" else GROUP_MASHHAD_WAITING
    return normalize_group_chat_id(chat_id)


def branch_display_name(branch):
    """نام نمایشی شعبه"""
    return "مشهد (خیام)" if branch == "mashhad" else "تهران (هتل پارسیان آزادی)"


def split_message_text(text, limit=3900):
    """شکستن متن‌های بلند به چند پیام (محدودیت ۴۰۹۶ کاراکتری تلگرام)"""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line[:limit]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def waiting_list_text(branch):
    """متن لیست کاربران در انتظار دریافت عکس (None اگر کسی در انتظار نباشد)"""
    rows = get_pending_requests_with_users(branch)
    if not rows:
        return None

    now_iran = iran_now()
    lines = [
        f"⏳ لیست کاربران در انتظار دریافت عکس — شعبه {branch_display_name(branch)}",
        f"🕐 زمان گزارش: {now_iran.strftime('%Y/%m/%d - %H:%M')}",
        f"📊 تعداد در انتظار: {len(rows)} نفر",
        "",
        "──────────────────",
    ]

    for index, row in enumerate(rows, start=1):
        hours = int(row.get("hours") or 0)
        if hours >= 24:
            waiting_text = f"{hours // 24} روز"
        else:
            waiting_text = f"{hours} ساعت"

        lines.append(
            f"{index}) 👤 {format_user_display(row['user_id'], row.get('first_name'), row.get('username'))}"
        )
        lines.append(
            f"   🗓 عضویت در ربات: {format_persian_datetime(row.get('joined_at'), with_time=False)}"
        )
        lines.append(f"   📱 شماره: {row['phone']} | 🏷️ کد عکس: {row['photo_code']}")
        lines.append(
            f"   📅 تاریخ عکس: {row.get('photo_date') or 'نامشخص'} | ⏰ در انتظار: {waiting_text}"
        )
        lines.append("")

    lines.append(
        f"✅ این لیست هر {WAITING_LIST_INTERVAL_HOURS} ساعت یک‌بار ارسال می‌شود و با "
        "ارسال هر عکس، درخواست مربوطه از این لیست حذف می‌شود."
    )
    return "\n".join(lines)


async def send_waiting_list_to_group(bot, branch):
    """ارسال لیست کاربران در انتظار دریافت عکس به گروه لیست انتظار شعبه"""
    chat_id = waiting_group_chat_id(branch)
    if not chat_id:
        print(f"⚠️ آیدی گروه لیست انتظار شعبه {branch} تنظیم نشده است.")
        return False

    text = waiting_list_text(branch)
    if not text:
        print(f"ℹ️ لیست انتظار شعبه {branch} خالی است؛ پیامی ارسال نشد.")
        return False

    for chunk in split_message_text(text):
        await bot.send_message(chat_id=chat_id, text=chunk)
    return True


async def notify_waiting_group(
    context, user, branch, phone, photo_code, photo_date, photo_sent=False
):
    """اطلاع‌رسانی درخواست جدید در گروه لیست انتظار شعبه مربوطه"""
    chat_id = waiting_group_chat_id(branch)
    if not chat_id:
        print(f"⚠️ آیدی گروه لیست انتظار شعبه {branch} تنظیم نشده است.")
        return False

    user_record = get_user_record(user.id) or {}
    status_line = (
        "✅ عکس این کاربر از قبل آپلود شده بود و به‌صورت خودکار برای او ارسال شد."
        if photo_sent
        else "⏳ لطفا عکس این کاربر ارسال شود."
    )

    now_iran = iran_now()
    text = (
        "📸 درخواست عکس یادگاری جدید\n\n"
        f"📍 شعبه: {branch_display_name(branch)}\n"
        f"👤 کاربر: {format_user_display(user.id, getattr(user, 'first_name', None), getattr(user, 'username', None))}\n"
        f"🗓 عضویت در ربات: {format_persian_datetime(user_record.get('joined_at'))}\n"
        f"📱 شماره: {phone}\n"
        f"🏷️ کد عکس: {photo_code}\n"
        f"📅 تاریخ عکس: {photo_date or 'نامشخص'}\n"
        f"🕐 زمان درخواست: {now_iran.strftime('%Y/%m/%d - %H:%M')}\n\n"
        f"{status_line}"
    )

    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیام به گروه لیست انتظار شعبه {branch}: {e}")
        return False


async def handle_new_photo_request(
    context, user, branch, phone, photo_code, photo_date, photo_sent=False
):
    """لاگ درخواست جدید + اطلاع‌رسانی به گروه لیست انتظار شعبه"""
    log_photo_request_activity(user, phone, photo_code, branch)
    await notify_waiting_group(
        context,
        user,
        branch,
        phone,
        photo_code,
        photo_date,
        photo_sent=photo_sent,
    )


async def waiting_list_scheduler(app):
    """ارسال دوره‌ای لیست کاربران در انتظار دریافت عکس به گروه‌های لیست انتظار"""
    interval_seconds = max(300, int(float(WAITING_LIST_INTERVAL_HOURS) * 3600))
    print(
        "⏰ ارسال دوره‌ای لیست انتظار فعال شد "
        f"(هر {WAITING_LIST_INTERVAL_HOURS} ساعت) | "
        f"مشهد: {waiting_group_chat_id('mashhad')} | "
        f"تهران: {waiting_group_chat_id('tehran')}"
    )

    while True:
        await asyncio.sleep(interval_seconds)
        for branch in ("mashhad", "tehran"):
            try:
                await send_waiting_list_to_group(app.bot, branch)
            except Exception as e:
                print(f"❌ خطا در ارسال لیست انتظار شعبه {branch}: {e}")


async def on_startup(app):
    """کارهای بعد از آماده شدن ربات (شروع زمان‌بند لیست انتظار)"""
    asyncio.create_task(waiting_list_scheduler(app))


async def real_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        print(f"🔍 وضعیت کاربر: {member.status}")
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"❌ خطا در بررسی عضویت: {e}")
        return False


async def send_preuploaded_file(context, chat_id, file_id, file_type=None):
    file_type = (file_type or "photo").lower()
    caption = PHOTO_DELIVERED_MESSAGE

    if file_type == "document":
        try:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown",
            )
            return True
        except Exception as e:
            print(f"❌ تلاش اول برای send_document ناموفق بود: {e}")
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode="Markdown",
                )
                return True
            except Exception as second_error:
                print(
                    f"❌ هر دو روش ارسال عکس/فایل برای preuploaded ناموفق بود: {second_error}"
                )
                raise second_error

    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=file_id,
            caption=caption,
            parse_mode="Markdown",
        )
        return True
    except Exception as e:
        print(f"❌ تلاش اول برای send_photo ناموفق بود: {e}")
        try:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown",
            )
            return True
        except Exception as second_error:
            print(
                f"❌ هر دو روش ارسال عکس/فایل برای preuploaded ناموفق بود: {second_error}"
            )
            raise second_error


BTN_ADD_ADMIN = KeyboardButton("➕ افزودن ادمین")
BTN_REMOVE_ADMIN = KeyboardButton("➖ حذف ادمین")
BTN_LIST_ADMINS = KeyboardButton("📋 لیست ادمین‌ها")

BTN_JOIN = InlineKeyboardButton("عضویت در کانال", url="https://t.me/pesaranekarim")
BTN_CHECK = InlineKeyboardButton("بررسی عضویت", callback_data="check")

BTN_MASHHAD = KeyboardButton("شعبه مشهد(خیام)")
BTN_TEHRAN = KeyboardButton("شعبه تهران(هتل پارسیان آزادی)")

BTN_MASHHAD_PHOTO = KeyboardButton("دریافت عکس یادگاری")
BTN_MASHHAD_APP = KeyboardButton("اپلیکیشن پسران کریم")
BTN_MASHHAD_MENU = KeyboardButton("منو به همراه قیمت")
BTN_MASHHAD_FULL_MENU = KeyboardButton("منو به همراه تصویر")
BTN_MASHHAD_ORDER = KeyboardButton("سفارش آنلاین")
BTN_MASHHAD_PHONE_ORDER = KeyboardButton("سفارش تلفنی و رزرو مجالس")
BTN_MASHHAD_LOCATION = KeyboardButton("مسیریابی(لوکیشن)")
BTN_MASHHAD_ADDRESS = KeyboardButton("آدرس ما")
BTN_MASHHAD_SOCIAL = KeyboardButton("شبکه های اجتماعی ما")
BTN_MASHHAD_HISTORY = KeyboardButton("تاریخچه پسران کریم")
BTN_CHANGE_BRANCH = KeyboardButton("تغییر شعبه")


BTN_TEHRAN_PHOTO = KeyboardButton("دریافت عکس یادگاری")
BTN_TEHRAN_APP = KeyboardButton("اپلیکیشن پسران کریم")
BTN_TEHRAN_MENU = KeyboardButton("منو به همراه قیمت")
BTN_TEHRAN_FULL_MENU = KeyboardButton("منو به همراه تصویر")
BTN_TEHRAN_ORDER = KeyboardButton("سفارش آنلاین")
BTN_TEHRAN_PHONE_ORDER = KeyboardButton("سفارش تلفنی و رزرو مجالس")
BTN_TEHRAN_LOCATION = KeyboardButton("مسیریابی(لوکیشن)")
BTN_TEHRAN_ADDRESS = KeyboardButton("آدرس ما")
BTN_TEHRAN_SOCIAL = KeyboardButton("شبکه های اجتماعی ما")
BTN_TEHRAN_HISTORY = KeyboardButton("تاریخچه پسران کریم")
BTN_CHANGE_BRANCH = KeyboardButton("تغییر شعبه")
BTN_SUPPORT = KeyboardButton("پشتیبانی")

BTN_BACK_TEXT = "بازگشت"
BTN_BACK = KeyboardButton(BTN_BACK_TEXT)
BTN_ADMIN_BACK_TEXT = BTN_BACK_TEXT

BTN_ADMIN_PANEL = KeyboardButton("🛠️ پنل مدیریت")
BTN_ADMIN_STATS = KeyboardButton("آمار")
BTN_ADMIN_MASHHAD_PENDING = KeyboardButton("⏳ در انتظار - مشهد")
BTN_ADMIN_TEHRAN_PENDING = KeyboardButton("⏳ در انتظار - تهران")
BTN_ADMIN_MASHHAD_FAILED = KeyboardButton("❌ ارسال ناموفق - مشهد")
BTN_ADMIN_TEHRAN_FAILED = KeyboardButton("❌ ارسال ناموفق - تهران")
BTN_ADMIN_RESEND = KeyboardButton("ارسال مجدد")
BTN_ADMIN_MANAGE = KeyboardButton("👥 مدیریت ادمین‌ها")
BTN_ADMIN_USERS_LOG = KeyboardButton("📋 کاربران ربات")
BTN_ADMIN_USAGE_LOG = KeyboardButton("🧾 لاگ استفاده از ربات")
BTN_ADMIN_SEND_WAITING_LIST = KeyboardButton("📤 ارسال لیست انتظار")
BTN_ADMIN_REWARD_CLAIMS = KeyboardButton("🎁 دریافت‌های ۱۰ امتیاز")
BTN_ADMIN_REVIEW_GIF = KeyboardButton("🎬 گیف نظرسنجی")
BTN_ADMIN_BACK = KeyboardButton("🔙 بازگشت به منو")

# ===== دکمه‌های ثبت گیف نظرسنجی هر شعبه (پنل مدیریت) =====
BTN_GIF_MASHHAD = KeyboardButton("🎬 گیف مشهد")
BTN_GIF_TEHRAN = KeyboardButton("🎬 گیف تهران")
BTN_GIF_DELETE_MASHHAD = KeyboardButton("🗑 حذف گیف مشهد")
BTN_GIF_DELETE_TEHRAN = KeyboardButton("🗑 حذف گیف تهران")

BTN_YES = KeyboardButton("بله، عکس دیگری دارم")
BTN_NO = KeyboardButton("نه، تمام شد")

# ===== دکمه‌های نظرسنجی =====
BTN_SURVEY_YES = KeyboardButton("بله، ۵ ستاره میدم")
BTN_SURVEY_NO = KeyboardButton("خیر")

# متن‌هایی که به عنوان پاسخ «بله» یا «خیر» در نظرسنجی پذیرفته می‌شوند
SURVEY_YES_TEXTS = {
    BTN_SURVEY_YES.text,
    "بله",
    "بله ۵ ستاره میدم",
    "۵ ستاره میدم",
    "بله، راضی بودم",
}
SURVEY_NO_TEXTS = {
    BTN_SURVEY_NO.text,
    "نه",
    "نه، راضی نبودم",
    "خیر، راضی نبودم",
    "راضی نبودم",
}

BTN_STAR_1 = KeyboardButton("⭐")
BTN_STAR_2 = KeyboardButton("⭐⭐")
BTN_STAR_3 = KeyboardButton("⭐⭐⭐")
BTN_STAR_4 = KeyboardButton("⭐⭐⭐⭐")
BTN_STAR_5 = KeyboardButton("⭐⭐⭐⭐⭐")

MONTHS = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

SUPPORT_USERNAME = "pesaranekarimphotos"

# ===== پیام تحویل عکس یادگاری =====
# این پیام بلافاصله بعد از ارسال عکس برای مشتری فرستاده می‌شود و بعد از آن
# نظرسنجی رضایت شروع می‌شود.
PHOTO_DELIVERED_MESSAGE = (
    "فایل اصلی عکستون با کیفیت بالا تقدیم محضر باسعادتتون🙏😇🌹\n\n"
    "سپاس از یادگاری که گذاشتید و قوت قلبی که بخشیدید🌺\n"
    "اگر دوست دارین عکس زیباتون در اینستاگرام ما استوری شود کافیه اونو استوری کنید و آیدی ما دراینستاگرام را\n"
    "(@pesaranekarim)\n"
    "زیرش تگ کنین👌\n"
    "یادتون نره حتما هم مارو فالو داشته باشید برای اطلاع از تخفیفات و اطلاعیه ها👇\n"
    "Instagram.com/pesaranekarim\n"
    "به سایتمون هم حتما سر بزنین😉🌹\n"
    "www.pesaranekarim.rest"
)

# ===== پیامهای نظرسنجی =====
SURVEY_FIVE_STAR_QUESTION = "📊 نظرسنجی رضایت\n\nاز ۵ ستاره به ما ۵ ستاره می‌دهید؟"

GOOGLE_REVIEW_MESSAGE = (
    "ضمن عرض تشکر و قدردانی از رضایت شما\n"
    "لینک کاملا رسمی و قانونی در گوگل مپ جهت اعلام نظر شما طراحی شده است\n"
    "لطفا به این لینک ورود کرده و ضمن اعلام نظرتون در مورد کم و کِیف عملکرد رستوران، نمره ۵ ستاره را برای ما داخل گوگل مپ به یادگار بگذارید\n"
    "این کار بالاترین هدیه شماست در جهت رشد روزافزون ما\n"
    "👇لینک نظر دهی👇"
)


def google_review_message(branch):
    """متن پیام تشکر بالای گیف (بدون لینک گوگل مپ)"""
    return GOOGLE_REVIEW_MESSAGE


LOW_RATING_REQUEST_MESSAGE = (
    "متاسفیم که تجربه شما مطابق انتظار ما نبوده🙏\n\n"
    "لطفا از ۱ تا ۴ ستاره به ما امتیاز دهید:"
)

LOW_RATING_REASON_REQUEST_MESSAGE = (
    "چنانچه انتقادی،پیشنهادی و یا فرمایشی دارید خوشحال میشیم بشنویم🙏🌹"
)

# پیامی که بعد از نوشتن انتقاد/پیشنهاد برای کاربر فرستاده می‌شود
LOW_RATING_THANKS_MESSAGE = (
    "حتما تمامی مواردی که فرمودین رو پیگیری میکنیم\n"
    " ممنون از وقتی که گذاشتید و  امیدواریم مجددا توفیق میزبانی شمارو داشته باشیم و اینبار با رضایت کامل شما🙏💛"
)

REWARD_INVITE_MESSAGE = (
    f"🎁 هدیه {REWARD_POINTS} امتیازی\n\n"
    f"اگر نظر ۵ ستاره خود را در گوگل مپ ثبت کردید، با دکمه زیر {REWARD_POINTS} امتیاز هدیه بگیرید:"
)

REWARD_THANKS_MESSAGE = "از مهر ماندگار شما صمیمانه سپاسگزاریم و امیدواریم بتونیم مجددا توفیق میزبانی شمارو داشته باشیم🙏😇🌸"

# پیام پایانی بعد از زدن دکمه «✅ نظر دادم» (فقط همین یک پیام ارسال می‌شود)
REWARD_CONGRATS_MESSAGE = (
    "🎉 تبریک!\n"
    f"شما {REWARD_POINTS} امتیاز هدیه گرفتید!\n\n"
    "از مهر ماندگار شما صمیمانه سپاسگزاریم و امیدواریم بتونیم مجددا توفیق میزبانی شمارو داشته باشیم!🙏😇🌸"
)

# اگر ارسال/کپی پیام گیف ممکن نبود، این متن با دکمه «✅ نظر دادم» فرستاده می‌شود
REVIEW_GIF_FALLBACK_MESSAGE = "📍 لطفا نظر خود را درباره کم و کِیف عملکرد رستوران ثبت کنید و پس از آن روی دکمه زیر بزنید👇"

# متن دکمه‌های ثبت/حذف گیف نظرسنجی هر شعبه
REVIEW_GIF_SET_TEXTS = {
    BTN_GIF_MASHHAD.text: "mashhad",
    BTN_GIF_TEHRAN.text: "tehran",
}
REVIEW_GIF_DELETE_TEXTS = {
    BTN_GIF_DELETE_MASHHAD.text: "mashhad",
    BTN_GIF_DELETE_TEHRAN.text: "tehran",
}


def google_map_link(branch):
    """لینک نظر دهی در گوگل مپ برای هر شعبه"""
    return GOOGLE_MAP_TEHRAN if branch == "tehran" else GOOGLE_MAP_MASHHAD


def google_review_kb(branch):
    """دکمه لینک گوگل در این جریان حذف شده است؛ فقط دکمه «✅ نظر دادم» باقی می‌ماند."""
    return None


def review_done_keyboard(branch="mashhad"):
    """دکمه کیبورد «✅ نظر دادم» برای ارسال بعد از گیف نظرسنجی"""
    return ReplyKeyboardMarkup(
        [["✅ نظر دادم"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def review_done_kb(branch="mashhad"):
    """دکمه «نظر دادم» زیر گیف نظرسنجی - اکنون حذف شده"""
    return None


def review_gif_message_id(branch):
    """شماره پیام گیف نظرسنجی در گروه لیست انتظار شعبه"""
    try:
        if branch == "tehran":
            return int(REVIEW_GIF_MESSAGE_ID_TEHRAN)
        return int(REVIEW_GIF_MESSAGE_ID_MASHHAD)
    except (TypeError, ValueError):
        return None


def review_gif_kb():
    """دکمه‌های بخش ثبت گیف نظرسنجی در پنل مدیریت"""
    return ReplyKeyboardMarkup(
        [
            [BTN_GIF_MASHHAD, BTN_GIF_TEHRAN],
            [BTN_GIF_DELETE_MASHHAD, BTN_GIF_DELETE_TEHRAN],
            [BTN_ADMIN_BACK],
        ],
        resize_keyboard=True,
    )


def nshn_link_for(branch: str):
    return NSHN_TEHRAN if str(branch).lower() == "tehran" else NSHN_MASHHAD


def nshn_offer_message(branch: str):
    """Compose the NSHN offer message (50 points incentive)."""
    return (
        "🎁 پیشنهاد ویژه!\n\n"
        "اگر تجربه‌تون رو در اپلیکیشن «نشان» (نشون) برای این شعبه ثبت کنید، ما به‌عنوان قدردانی "
        f"{NSHN_REWARD_POINTS} امتیاز هدیه خواهیم داد.\n\n"
        "لطفا روی دکمه لینک زیر بزنید و نظرتون رو ثبت کنید؛ سپس پس از ۵ دقیقه دکمه «✅ نظر دادم نشان» "
        "برای دریافت امتیاز فعال می‌شود.\n\n"
        "از همراهی و حمایتشون بی‌نهایت سپاسگزاریم!🌸"
    )


NSHN_REWARD_CONGRATS_MESSAGE = (
    "🎉 تبریک!\n"
    f"شما {NSHN_REWARD_POINTS} امتیاز هدیه گرفتید!\n\n"
    "از مهر ماندگار شما صمیمانه سپاسگزاریم و امیدواریم بتونیم مجددا توفیق میزبانی شمارو داشته باشیم!🙏😇🌸"
)


async def send_nshn_offer(context, user_id, branch):
    """Send NSHN offer with link button and schedule the delayed claim keyboard."""
    try:
        nshn_link = nshn_link_for(branch)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 ثبت نظر در نشان", url=nshn_link)]]
        )
        await context.bot.send_message(chat_id=user_id, text=nshn_offer_message(branch), reply_markup=kb)

        async def delayed_claim():
            await asyncio.sleep(5 * 60)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="اگر در نشان نظر دادید دکمه را بزنید:",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton(NSHN_BUTTON_TEXT)]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
            except Exception as e:
                print(f"❌ خطا در ارسال دکمه نظر دادم نشان: {e}")

        asyncio.create_task(delayed_claim())
    except Exception as e:
        print(f"❌ خطا در ارسال پیشنهاد نشان: {e}")




def low_rating_kb():
    """دکمه‌های امتیاز ۱ تا ۴ ستاره برای مشتری ناراضی"""
    return ReplyKeyboardMarkup(
        [[BTN_STAR_4, BTN_STAR_3, BTN_STAR_2, BTN_STAR_1], [BTN_BACK]],
        resize_keyboard=True,
    )


def reward_received_text(branch, claims_count=None):
    """متن پیام تبریک و اعلام امتیاز بعد از ثبت نظر"""
    now = jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M")
    text = (
        "🎉 تبریک!\n"
        f"شما {REWARD_POINTS} امتیاز هدیه گرفتید!\n\n"
        "✅ سپاس از همراهی شما در حمایت از رستوران\n"
        f"📍 شعبه: {branch_display_name(branch)}\n"
        f" زمان ثبت: {now}"
    )
    if claims_count and claims_count > 1:
        text += f"\n\n🔹 این {claims_count}اُمین ثبت نظر شما در این شعبه است."
    return text


async def send_photo_delivered_message(context, user_id):
    """ارسال پیام تحویل عکس یادگاری به مشتری (قبل از شروع نظرسنجی)"""
    try:
        await context.bot.send_message(chat_id=user_id, text=PHOTO_DELIVERED_MESSAGE)
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیام تحویل عکس: {e}")
        return False


async def send_review_gif_file(context, chat_id, gif):
    """ارسال فایل گیف نظرسنجی (بدون دکمه)"""
    file_id = (gif or {}).get("file_id")
    if not file_id:
        raise ValueError("file_id گیف نظرسنجی مشخص نیست")

    caption = (gif or {}).get("caption") or None
    file_type = str((gif or {}).get("file_type") or "animation").strip().lower()

    send_order = {
        "animation": ("animation", "video", "document"),
        "video": ("video", "animation", "document"),
        "document": ("document", "animation", "video"),
    }.get(file_type, ("animation", "video", "document"))

    last_error = None
    for kind in send_order:
        try:
            if kind == "animation":
                await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=file_id,
                    caption=caption,
                )
            elif kind == "video":
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption,
                )
            else:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=file_id,
                    caption=caption,
                )
            return True
        except Exception as e:
            last_error = e
            print(f"❌ ارسال گیف نظرسنجی به شکل {kind} ناموفق بود: {e}")

    raise last_error


async def send_review_gif(context, chat_id, branch):
    """ارسال پیام گیف نظرسنجی (بدون دکمه)

    ۱) گیفی که مدیر در پنل مدیریت ثبت کرده باشد
    ۲) کپی پیام گیف موجود در گروه لیست انتظار همان شعبه
    ۳) پیام متنی جایگزین (اگر هیچ‌کدام ممکن نبود)
    """
    registered_gif = get_review_gif(branch)
    if registered_gif:
        try:
            await send_review_gif_file(context, chat_id, registered_gif)
            return True
        except Exception as e:
            print(f"❌ ارسال گیف ثبت‌شده شعبه {branch} ناموفق بود: {e}")

    source_chat_id = waiting_group_chat_id(branch)
    message_id = review_gif_message_id(branch)
    if source_chat_id and message_id:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
            )
            return True
        except Exception as e:
            print(f"❌ کپی پیام گیف گروه لیست انتظار شعبه {branch} ناموفق بود: {e}")

    await context.bot.send_message(chat_id=chat_id, text=REVIEW_GIF_FALLBACK_MESSAGE)
    return False


async def send_review_request_messages(context, chat_id, branch):
    """بعد از اعلام رضایت ۵ ستاره: پیام تشکر (بدون لینک و بدون دکمه) ← گیف ← دکمه «✅ نظر دادم»"""
    await context.bot.send_message(
        chat_id=chat_id,
        text=GOOGLE_REVIEW_MESSAGE,
    )
    await send_review_gif(context, chat_id, branch)
    await context.bot.send_message(
        chat_id=chat_id,
        text="اگر نظر خود را بیان کردید روی دکمه زیر کلیک کنید:",
        reply_markup=review_done_keyboard(branch),
    )


def admin_panel_kb():
    keyboard = [
        [BTN_ADMIN_STATS],
        [BTN_ADMIN_USERS_LOG, BTN_ADMIN_USAGE_LOG],
        [BTN_ADMIN_SEND_WAITING_LIST],
        [BTN_ADMIN_REWARD_CLAIMS, BTN_ADMIN_REVIEW_GIF],
        [BTN_ADMIN_MASHHAD_PENDING, BTN_ADMIN_TEHRAN_PENDING],
        [BTN_ADMIN_MASHHAD_FAILED, BTN_ADMIN_TEHRAN_FAILED],
        [BTN_ADMIN_RESEND],
        [BTN_ADMIN_MANAGE],
        [BTN_ADMIN_BACK],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def membership_kb():
    return make_keyboard([BTN_JOIN, BTN_CHECK], row_width=1)


def branch_kb():
    return ReplyKeyboardMarkup(
        [[BTN_MASHHAD, BTN_TEHRAN]], resize_keyboard=True, one_time_keyboard=True
    )


def mashhad_menu_kb(user_id=None):
    keyboard = [
        [BTN_MASHHAD_PHOTO],
        [BTN_MASHHAD_APP],
        [BTN_MASHHAD_MENU, BTN_MASHHAD_FULL_MENU],
        [BTN_MASHHAD_ORDER, BTN_MASHHAD_PHONE_ORDER],
        [BTN_MASHHAD_LOCATION, BTN_MASHHAD_ADDRESS],
        [BTN_MASHHAD_SOCIAL, BTN_MASHHAD_HISTORY],
        [BTN_CHANGE_BRANCH, BTN_SUPPORT],
    ]
    if user_id and is_admin(user_id):
        keyboard.insert(0, [BTN_ADMIN_PANEL])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def tehran_menu_kb(user_id=None):
    keyboard = [
        [BTN_TEHRAN_PHOTO],
        [BTN_TEHRAN_APP],
        [BTN_TEHRAN_MENU, BTN_TEHRAN_FULL_MENU],
        [BTN_TEHRAN_ORDER, BTN_TEHRAN_PHONE_ORDER],
        [BTN_TEHRAN_LOCATION, BTN_TEHRAN_ADDRESS],
        [BTN_TEHRAN_SOCIAL, BTN_TEHRAN_HISTORY],
        [BTN_CHANGE_BRANCH, BTN_SUPPORT],
    ]
    if user_id and is_admin(user_id):
        keyboard.insert(0, [BTN_ADMIN_PANEL])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def branch_menu_kb(branch=None, user_id=None):
    """منوی مربوط به شعبه؛ اگر کاربر ادمین/سازنده ربات باشد دکمه پنل مدیریت هم اضافه می‌شود"""
    if branch == "tehran":
        return tehran_menu_kb(user_id)
    return mashhad_menu_kb(user_id)


def is_leap_year(year):

    return jdatetime.date(year, 1, 1).isleap()


def get_days_in_month(year, month):
    if month <= 6:
        return 31
    elif month <= 11:
        return 30
    else:
        return 30 if is_leap_year(year) else 29


def get_current_persian_date():
    now = jdatetime.datetime.now()
    return now.year, now.month, now.day


def get_persian_years():
    current_year = get_current_persian_date()[0]
    years = []
    for year in range(1400, current_year + 1):
        years.append(str(year))
    return years


def get_max_month_for_year(year):
    """آخرین ماهی که برای این سال مجاز است انتخاب شود."""
    current_year, current_month, _ = get_current_persian_date()
    if year == current_year:
        return current_month
    return 12


def get_max_day_for_month(year, month):
    current_year, current_month, current_day = get_current_persian_date()

    if year == current_year and month == current_month:
        return current_day
    elif year == current_year and month > current_month:

        return 0
    else:
        return get_days_in_month(year, month)


def year_kb():
    years = get_persian_years()
    keyboard = []
    row = []
    for i, year in enumerate(years):
        row.append(KeyboardButton(year))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([BTN_BACK])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def month_kb(year=None):
    max_month = get_max_month_for_year(year) if year else 12
    keyboard = []
    row = []
    for i, month in enumerate(MONTHS):
        month_number = i + 1
        if month_number > max_month:
            continue
        row.append(KeyboardButton(month))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([BTN_BACK])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def day_kb(year, month):
    max_day = get_max_day_for_month(year, month)

    keyboard = []
    row = []
    for i in range(1, max_day + 1):
        row.append(KeyboardButton(str(i)))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([BTN_BACK])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این بخش ندارید.")
        return
    context.user_data["in_admin_panel"] = True
    await update.message.reply_text(
        "به پنل مدیریت خوش آمدید.\n\n" "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=admin_panel_kb(),
        parse_mode="Markdown",
    )


async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["admin_action"] = "add_admin"
    await update.message.reply_text(
        "➕ افزودن ادمین جدید\n\n"
        "لطفا آیدی عددی یا یوزرنیم ادمین جدید را وارد کنید:\n"
        "(مثلاً `123456789` یا `@joe`)",
        reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
        parse_mode="Markdown",
    )


async def admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    admins = get_all_admins()
    if not admins:
        await update.message.reply_text("هیچ ادمینی در سیستم وجود ندارد❌")
        return

    keyboard = []
    for admin in admins:
        admin_id = admin["user_id"]
        # ادمین اصلی و سازنده/مالک ربات قابل حذف نیستند
        if admin_id != update.effective_user.id and not is_super_admin(admin_id):
            username = admin.get("username")
            first_name = admin.get("first_name") or ""
            display_text = f"@{username}" if username else f"{first_name} ({admin_id})"
            keyboard.append([KeyboardButton(display_text)])

    if not keyboard:
        await update.message.reply_text("❌ هیچ ادمین دیگری برای حذف وجود ندارد.")
        return

    keyboard.append([BTN_ADMIN_BACK])
    context.user_data["admin_action"] = "remove_admin"

    await update.message.reply_text(
        "➖ حذف ادمین\n\n" "لطفا یکی از ادمین‌های زیر را برای حذف انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    admins = get_all_admins()
    if not admins:
        await update.message.reply_text("هیچ ادمینی در سیستم وجود ندارد❌")
        return

    text = "📋 لیست ادمین‌ها:\n\n"
    for i, admin in enumerate(admins, 1):
        admin_id = admin["user_id"]
        username = admin.get("username")
        first_name = admin.get("first_name") or ""
        last_name = admin.get("last_name") or ""
        if username:
            name_display = f"@{username}"
        elif first_name or last_name:
            name_display = f"{first_name} {last_name}".strip()
        else:
            name_display = str(admin_id)

        added_at = admin.get("added_at", "نامشخص")
        badge = " 👑 سازنده ربات" if is_super_admin(admin_id) else ""
        text += f"{i}. {name_display}{badge}\n   🆔 آیدی: `{admin_id}`\n   🕐 افزوده شده: {added_at}\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_preupload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["admin_action"] = "preupload"
    await update.message.reply_text(
        "📤 آپلود زودهنگام عکس\n\n"
        "لطفا شماره تلفن ۱۱ رقمی و کد ۴ رقمی مشتری را وارد کنید:\n"
        "(مثلاً `09123456789 1234`)\n\n"
        "سپس عکس را در گروه مربوطه آپلود کنید.",
        reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
        parse_mode="Markdown",
    )


async def admin_preupload_phone_code(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text

    if text == BTN_ADMIN_BACK_TEXT:
        context.user_data.pop("admin_action", None)
        await admin_command(update, context)
        return

    phone, photo_code = extract_phone_and_code(text)

    if not (phone.isdigit() and len(phone) == 11 and phone.startswith("09")):
        await update.message.reply_text(
            "❌ شماره تلفن معتبر نیست!\n"
            "لطفا شماره را به یکی از فرم‌های زیر وارد کنید:\n"
            "مثلاً `09123456789` یا `۰۹۱۲۳۴۵۶۷۸۹`"
        )
        return

    if not (photo_code.isdigit() and len(photo_code) == 4):
        await update.message.reply_text(
            "❌ کد عکس باید 4 رقمی باشد.\n" "مثلاً `1234` یا `۱۲۳۴`"
        )
        return

    context.user_data["preupload_phone"] = phone
    context.user_data["preupload_code"] = photo_code
    context.user_data["admin_action"] = "preupload_photo"

    await update.message.reply_text(
        f"✅ شماره `{phone}` و کد `{photo_code}` ثبت شد.\n\n"
        "📸 حالا لطفا عکس را در گروه مربوطه آپلود کنید.\n"
        f"📍 گروه {'مشهد' if context.user_data.get('branch', 'mashhad') == 'mashhad' else 'تهران'}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
    )


async def admin_preupload_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    photos = get_all_preuploaded_photos()

    if not photos:
        await update.message.reply_text("📭 هیچ عکس پیش‌آپلود شده‌ای وجود ندارد.")
        return

    text = "📋 لیست عکس‌های پیش‌آپلود شده:\n\n"
    for photo in photos:
        photo_id = photo[0]
        phone = photo[1]
        photo_code = photo[2]
        branch = photo[3]
        created_at = photo[4]
        used = photo[5]
        status = "✅ استفاده شده" if used else "⏳ در انتظار"
        branch_name = "مشهد" if branch == "mashhad" else "تهران"
        text += f"📱 {phone} - کد: {photo_code}\n"
        text += f"   📍 {branch_name} - {status}\n"
        text += f"   🕐 {created_at}\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_admin_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not is_admin(user_id):
        return

    if context.user_data.get("admin_action") == "add_admin":
        if text == BTN_ADMIN_BACK_TEXT:
            context.user_data.pop("admin_action", None)
            await admin_manage(update, context)
            return

        try:
            new_admin_id = None
            username = None
            first_name = None
            last_name = None

            if text.isdigit():
                new_admin_id = int(text)

                try:
                    user = await context.bot.get_chat(new_admin_id)
                    username = user.username
                    first_name = user.first_name
                    last_name = user.last_name
                except:
                    username = None
                    first_name = None
                    last_name = None

            else:

                clean_username = text.lstrip("@")

                if not clean_username or not clean_username.replace("_", "").isalnum():
                    await update.message.reply_text(
                        "❌ یوزرنیم وارد شده معتبر نیست.\n"
                        "لطفا یک یوزرنیم معتبر وارد کنید (مثلاً `@joe`).",
                        parse_mode="Markdown",
                    )
                    return

                try:
                    user = await context.bot.get_chat(f"@{clean_username}")
                    new_admin_id = user.id
                    username = user.username
                    first_name = user.first_name
                    last_name = user.last_name
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ کاربر با یوزرنیم `@{clean_username}` پیدا نشد.\n"
                        "لطفا مطمئن شوید یوزرنیم صحیح است.",
                        parse_mode="Markdown",
                    )
                    return

            if new_admin_id:
                if add_admin(new_admin_id, username, first_name, last_name, user_id):
                    display_name = f"@{username}" if username else str(new_admin_id)
                    await update.message.reply_text(
                        f"✅ ادمین `{display_name}` با موفقیت اضافه شد.",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        f"❌ کاربر قبلا ادمین است یا خطایی رخ داده.",
                        parse_mode="Markdown",
                    )
            else:
                await update.message.reply_text(
                    "❌ خطا در افزودن ادمین. لطفا دوباره تلاش کنید.",
                    parse_mode="Markdown",
                )

        except ValueError:
            await update.message.reply_text(
                "❌ لطفا یک آیدی عددی یا یوزرنیم معتبر وارد کنید.",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ خطا: {str(e)}\nلطفا دوباره تلاش کنید.", parse_mode="Markdown"
            )

        context.user_data.pop("admin_action", None)
        await admin_manage(update, context)
        return

    if context.user_data.get("admin_action") == "remove_admin":
        if text == BTN_ADMIN_BACK_TEXT:
            context.user_data.pop("admin_action", None)
            await admin_manage(update, context)
            return

        try:
            admin_id_to_remove = None

            if text.isdigit():
                admin_id_to_remove = int(text)
            else:

                clean_username = text.lstrip("@")
                try:
                    user = await context.bot.get_chat(f"@{clean_username}")
                    admin_id_to_remove = user.id
                except:
                    await update.message.reply_text(
                        f"❌ کاربر با یوزرنیم `@{clean_username}` پیدا نشد.",
                        parse_mode="Markdown",
                    )
                    return

            if is_super_admin(admin_id_to_remove):
                await update.message.reply_text(
                    "❌ این کاربر سازنده/مالک ربات است و قابل حذف نیست."
                )
                context.user_data.pop("admin_action", None)
                await admin_manage(update, context)
                return

            if admin_id_to_remove == user_id:
                await update.message.reply_text("❌ نمی‌توانید خودتان را حذف کنید!")
                return

            if remove_admin(admin_id_to_remove):
                await update.message.reply_text(
                    f"✅ ادمین با موفقیت حذف شد.", parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"❌ کاربر مورد نظر ادمین نیست.", parse_mode="Markdown"
                )

        except ValueError:
            await update.message.reply_text(
                "❌ لطفا یک آیدی عددی یا یوزرنیم معتبر وارد کنید.",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {str(e)}", parse_mode="Markdown")

        context.user_data.pop("admin_action", None)
        await admin_manage(update, context)
        return


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    stats = get_daily_stats()
    reward_stats = get_review_rewards_stats()
    await update.message.reply_text(
        f"📊 آمار امروز\n\n"
        f"درخواست‌های ثبت‌شده: {stats['total_requests']}\n"
        f"✅ عکس‌های ارسال‌شده: {stats['sent_requests']}\n"
        f"⏳ در انتظار: {stats['pending_requests']}\n"
        f"❌ ارسال ناموفق: {stats['failed_requests']}\n\n"
        f"میانگین امتیاز رضایت: {stats['avg_rating']:.1f} از 5\n"
        f"🌟 تعداد 5 ستاره: {stats['five_star']}\n"
        f"تعداد نارضایتی (زیر 5): {stats['complaints']}\n\n"
        f"🎁 دریافت {REWARD_POINTS} امتیاز امروز: {reward_stats['claims_today']}\n"
        f"🎁 کل دریافت‌ها: {reward_stats['total_claims']}",
        parse_mode="Markdown",
    )


async def admin_users_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کاربران ربات همراه با تاریخ عضویت‌شان در ربات"""
    if not is_admin(update.effective_user.id):
        return

    text, keyboard = build_users_log_page(0)
    await update.message.reply_text(text, reply_markup=keyboard)


async def admin_usage_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لاگ استفاده از ربات: چه کسی، چه زمانی و با چه تاریخ عضویتی"""
    if not is_admin(update.effective_user.id):
        return

    text, keyboard = build_usage_log_page(0)
    await update.message.reply_text(text, reply_markup=keyboard)


async def admin_send_waiting_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال دستی لیست کاربران در انتظار دریافت عکس به گروه‌های لیست انتظار"""
    if not is_admin(update.effective_user.id):
        return

    results = []
    for branch in ("mashhad", "tehran"):
        try:
            sent = await send_waiting_list_to_group(context.bot, branch)
        except Exception as e:
            print(f"❌ خطا در ارسال لیست انتظار شعبه {branch}: {e}")
            sent = False

        if sent:
            results.append(f"✅ {branch_display_name(branch)}: لیست ارسال شد")
        else:
            results.append(f"ℹ️ {branch_display_name(branch)}: کسی در انتظار نیست")

    await update.message.reply_text(
        "📤 لیست کاربران در انتظار دریافت عکس\n\n" + "\n".join(results),
        reply_markup=admin_panel_kb(),
    )


async def admin_reward_claims(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست مشتریانی که دکمه دریافت ۱۰ امتیاز را زده‌اند (برای بررسی نظر ۵ ستاره)"""
    if not is_admin(update.effective_user.id):
        return

    stats = get_review_rewards_stats()
    total = get_review_rewards_count()
    claims = get_review_rewards(limit=REWARD_CLAIMS_PAGE_SIZE)

    lines = [
        f"🎁 اعلام‌های دریافت {REWARD_POINTS} امتیاز",
        "",
        f"📊 کل اعلام‌ها: {stats['total_claims']}",
        f"🆕 اعلام امروز: {stats['claims_today']}",
        f"👥 کاربران یکتا: {stats['unique_users']}",
        "──────────────────",
    ]

    if not claims:
        lines.append("هنوز کسی دکمه دریافت امتیاز را نزده است.")
    else:
        for index, claim in enumerate(claims, start=1):
            lines.append(
                f"{index}) 👤 {format_user_display(claim['user_id'], claim.get('first_name'), claim.get('username'))}"
            )
            lines.append(
                f"   📱 شماره: {claim.get('phone') or 'ثبت نشده'}"
                f" | 📍 {branch_display_name(claim.get('branch'))}"
            )
            lines.append(
                f"   🕐 زمان اعلام: {format_persian_datetime(claim.get('claimed_at'))}"
            )
            lines.append("")

        if total > len(claims):
            lines.append(f"… و {total - len(claims)} اعلام قدیمی‌تر.")
        lines.append(
            "🔹 این افراد اعلام کرده‌اند نظر ۵ ستاره خود را در گوگل مپ ثبت کرده‌اند؛ "
            "لطفا ثبت واقعی نظرشان بررسی شود."
        )

    await update.message.reply_text("\n".join(lines), reply_markup=admin_panel_kb())


async def admin_review_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بخش ثبت گیف نظرسنجی (گیفی که بعد از اعلام رضایت ۵ ستاره ارسال می‌شود)"""
    if not is_admin(update.effective_user.id):
        return

    context.user_data.pop("admin_action", None)
    context.user_data.pop("review_gif_branch", None)

    lines = ["🎬 گیف نظرسنجی شعبه‌ها", ""]
    for branch in ("mashhad", "tehran"):
        gif = get_review_gif(branch)
        source = (
            "گیف ثبت‌شده در پنل مدیریت"
            if gif
            else f"پیام گروه لیست انتظار (شماره {review_gif_message_id(branch)})"
        )
        lines.append(f"📍 {branch_display_name(branch)}: {source}")

    lines.extend(
        [
            "",
            "برای تغییر گیف، اول دکمه شعبه را بزنید و بعد گیف/ویدیو را همین‌جا "
            "(میتوانید پیام گروه را فوروارد کنید) ارسال کنید.",
            "اگر کپشنی هم بنویسید، همراه گیف برای مشتری ارسال می‌شود.",
        ]
    )

    await update.message.reply_text("\n".join(lines), reply_markup=review_gif_kb())


async def handle_review_gif_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب شعبه برای ثبت یا حذف گیف نظرسنجی"""
    if not is_admin(update.effective_user.id):
        return

    text = update.message.text

    if text in REVIEW_GIF_SET_TEXTS:
        branch = REVIEW_GIF_SET_TEXTS[text]
        context.user_data["admin_action"] = "review_gif"
        context.user_data["review_gif_branch"] = branch
        await update.message.reply_text(
            f"🎬 ثبت گیف نظرسنجی {branch_display_name(branch)}\n\n"
            "لطفا گیف یا ویدیوی مورد نظر را همین‌جا ارسال کنید.\n"
            "🔹 اگر کپشن بنویسید، همراه گیف برای مشتری ارسال می‌شود.\n\n"
            "برای انصراف دکمه «بازگشت به منو» را بزنید.",
            reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
        )
        return

    if text in REVIEW_GIF_DELETE_TEXTS:
        branch = REVIEW_GIF_DELETE_TEXTS[text]
        removed = clear_review_gif(branch)
        context.user_data.pop("admin_action", None)
        context.user_data.pop("review_gif_branch", None)

        if removed:
            message = (
                f"✅ گیف ثبت‌شده {branch_display_name(branch)} حذف شد.\n\n"
                "از این پس پیام گیف گروه لیست انتظار همین شعبه برای مشتری کپی می‌شود."
            )
        else:
            message = (
                f"ℹ️ برای {branch_display_name(branch)} گیفی در پنل ثبت نشده بود؛ "
                "پیام گیف گروه لیست انتظار استفاده می‌شود."
            )

        await update.message.reply_text(message, reply_markup=review_gif_kb())
        return


async def handle_review_gif_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت گیف نظرسنجی توسط ادمین (انیمیشن/ویدیو/فایل) در چت خصوصی"""
    if context.user_data.get("admin_action") != "review_gif":
        return

    if not is_admin(update.effective_user.id):
        return

    message = update.message
    branch = context.user_data.get("review_gif_branch", "mashhad")

    file_id = None
    file_type = None
    if getattr(message, "animation", None):
        file_id, file_type = message.animation.file_id, "animation"
    elif getattr(message, "video", None):
        file_id, file_type = message.video.file_id, "video"
    elif getattr(message, "document", None):
        file_id, file_type = message.document.file_id, "document"

    if not file_id:
        await message.reply_text(
            "❌ لطفا یک گیف، ویدیو یا فایل ویدیویی ارسال کنید.",
            reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
        )
        return

    caption = (getattr(message, "caption", None) or "").strip() or None

    if save_review_gif(branch, file_id, file_type, caption):
        await message.reply_text(
            f"✅ گیف نظرسنجی {branch_display_name(branch)} ثبت شد.\n\n"
            "از این پس این گیف همراه دکمه لینک گوگل مپ برای مشتریان ارسال می‌شود.",
            reply_markup=review_gif_kb(),
        )
        context.user_data.pop("admin_action", None)
        context.user_data.pop("review_gif_branch", None)
    else:
        await message.reply_text("❌ خطا در ثبت گیف. لطفا دوباره تلاش کنید.")


def _parse_log_callback_offset(callback_data):
    """استخراج شماره صفحه از داده دکمه‌های صفحه‌بندی لاگ"""
    try:
        return int(str(callback_data).split(":")[1])
    except (IndexError, ValueError):
        return 0


async def users_log_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحه‌بندی لیست کاربران ربات"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    offset = _parse_log_callback_offset(query.data)
    text, keyboard = build_users_log_page(offset)
    await query.edit_message_text(text, reply_markup=keyboard)


async def usage_log_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحه‌بندی لاگ استفاده از ربات"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    offset = _parse_log_callback_offset(query.data)
    text, keyboard = build_usage_log_page(offset)
    await query.edit_message_text(text, reply_markup=keyboard)


def _clamp_log_offset(offset, total, page_size):
    """محدود کردن شماره صفحه در بازه مجاز"""
    max_offset = ((max(total, 1) - 1) // page_size) * page_size
    return max(0, min(offset, max_offset))


def _log_page_keyboard(callback_prefix, offset, page_size, total):
    """دکمه‌های صفحه‌بندی لاگ‌ها"""
    buttons = []
    if offset > 0:
        buttons.append(
            InlineKeyboardButton(
                "⬅️ صفحه قبل",
                callback_data=f"{callback_prefix}:{max(0, offset - page_size)}",
            )
        )
    if offset + page_size < total:
        buttons.append(
            InlineKeyboardButton(
                "صفحه بعد ➡️",
                callback_data=f"{callback_prefix}:{offset + page_size}",
            )
        )
    return InlineKeyboardMarkup([buttons]) if buttons else None


def build_users_log_page(offset=0):
    """ساخت متن صفحه کاربران ربات همراه با تاریخ عضویت هر کاربر"""
    total = get_users_count()
    if total == 0:
        return "📋 هنوز هیچ کاربری در ربات ثبت نشده است.", None

    offset = _clamp_log_offset(offset, total, USERS_LOG_PAGE_SIZE)
    users = get_users_log(limit=USERS_LOG_PAGE_SIZE, offset=offset)
    stats = get_users_stats()

    lines = [
        "📋 کاربران ربات",
        "",
        f"👥 کل کاربران: {stats['total_users']}",
        f"🆕 عضویت امروز: {stats['new_users_today']}",
        f"🟢 کاربران فعال امروز: {stats['active_users_today']}",
        f"📊 کل استفاده از ربات: {stats['total_usage']}",
        "",
        "──────────────────",
    ]

    for index, user in enumerate(users, start=offset + 1):
        lines.append(
            f"{index}) 👤 {format_user_display(user['user_id'], user.get('first_name'), user.get('username'))}"
        )
        lines.append(
            f"   🗓 عضویت در ربات: {format_persian_datetime(user.get('joined_at'))}"
        )
        lines.append(
            f"   🕐 آخرین فعالیت: {format_persian_datetime(user.get('last_seen'))}"
        )
        lines.append(
            f"   📊 تعداد استفاده: {user.get('usage_count') or 0}"
            f" | 📸 درخواست عکس: {user.get('requests_count') or 0}"
        )
        lines.append("")

    total_pages = ((total - 1) // USERS_LOG_PAGE_SIZE) + 1
    lines.append(f"📄 صفحه {(offset // USERS_LOG_PAGE_SIZE) + 1} از {total_pages}")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n…"

    return text, _log_page_keyboard("users_log", offset, USERS_LOG_PAGE_SIZE, total)


def build_usage_log_page(offset=0):
    """ساخت متن صفحه لاگ استفاده از ربات (چه کسی، چه زمانی و تاریخ عضویتش)"""
    total = get_usage_logs_count()
    if total == 0:
        return "🧾 هنوز هیچ استفاده‌ای از ربات ثبت نشده است.", None

    offset = _clamp_log_offset(offset, total, USAGE_LOG_PAGE_SIZE)
    logs = get_usage_logs(limit=USAGE_LOG_PAGE_SIZE, offset=offset)
    stats = get_users_stats()

    lines = [
        "🧾 لاگ استفاده از ربات",
        "",
        f"📊 استفاده امروز: {stats['usage_today']}",
        f"🟢 کاربران فعال امروز: {stats['active_users_today']}",
        f"👣 کل استفاده‌ها: {stats['total_usage']}",
        "",
        "──────────────────",
    ]

    for index, item in enumerate(logs, start=offset + 1):
        lines.append(f"{index}) 🕐 {format_persian_datetime(item.get('created_at'))}")
        lines.append(
            f"   👤 {format_user_display(item['user_id'], item.get('first_name'), item.get('username'))}"
        )
        lines.append(
            f"   🗓 عضویت در ربات: {format_persian_datetime(item.get('joined_at'), with_time=False)}"
        )
        lines.append(f"   📌 عمل انجام‌شده: {item.get('action') or 'نامشخص'}")
        if item.get("detail"):
            lines.append(f"   📝 {item['detail']}")
        lines.append("")

    total_pages = ((total - 1) // USAGE_LOG_PAGE_SIZE) + 1
    lines.append(f"📄 صفحه {(offset // USAGE_LOG_PAGE_SIZE) + 1} از {total_pages}")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n…"

    return text, _log_page_keyboard("usage_log", offset, USAGE_LOG_PAGE_SIZE, total)


async def admin_pending_branch(
    update: Update, context: ContextTypes.DEFAULT_TYPE, branch: str
):
    if not is_admin(update.effective_user.id):
        return
    results = get_pending_requests(branch)
    branch_name = "مشهد" if branch == "mashhad" else "تهران"
    if not results:
        await update.message.reply_text(
            f"هیچ درخواست در انتظاری در شعبه {branch_name} وجود ندارد."
        )
        return

    text = f"⏳ درخواست‌های در انتظار - شعبه {branch_name}\n\n"
    for row in results:
        if len(row) >= 6:
            id, phone, code, date, created_at, hours = row
            if hours > 24:
                text += f"⚠️ {int(hours/24)} روز پیش — {phone} — {code}\n"
            else:
                text += f"🕐 {int(hours)} ساعت پیش — {phone} — {code}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_failed_branch(
    update: Update, context: ContextTypes.DEFAULT_TYPE, branch: str
):
    if not is_admin(update.effective_user.id):
        return

    results = get_failed_requests(branch)
    branch_name = "مشهد" if branch == "mashhad" else "تهران"

    if not results:
        await update.message.reply_text(
            f"هیچ ارسال ناموفقی در شعبه {branch_name} وجود ندارد."
        )
        return

    text = f"❌ ارسال‌های ناموفق - شعبه {branch_name}\n\n"
    for row in results:
        if len(row) >= 6:
            id, phone, code, date, created_at, reason = row
            text += f"{phone} — کد {code}\n"
    text += "\n⚠️ لطفا از راه دیگر با مشتری در ارتباط باشید."

    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_resend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["admin_action"] = "resend"
    await update.message.reply_text(
        "📤 ارسال مجدد عکس\n\n" "لطفا شماره تلفن ۱۱ رقمی مشتری را وارد کنید:",
        reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
    )


async def admin_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    context.user_data.pop("admin_action", None)
    keyboard = ReplyKeyboardMarkup(
        [
            [BTN_ADD_ADMIN],
            [BTN_REMOVE_ADMIN],
            [BTN_LIST_ADMINS],
            [BTN_ADMIN_BACK],
        ],
        resize_keyboard=True,
    )

    await update.message.reply_text(
        "👥 مدیریت ادمین‌ها\n\n" "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    branch = context.user_data.get("branch", "mashhad")
    await query.edit_message_text("🔙 به منوی اصلی بازگشتید.", reply_markup=None)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=branch_menu_kb(branch, query.from_user.id),
    )


async def claim_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه «✅ نظر دادم» بعد از ثبت نظر ۵ ستاره در گوگل مپ"""
    query = update.callback_query
    if query is None:
        return

    raw_data = str(query.data or "").strip()
    if not raw_data.startswith("claim_reward"):
        return

    user_id = query.from_user.id
    branch = "tehran" if "tehran" in raw_data else "mashhad"

    # ۱) اعلان فوری به کاربر: «تبریک، شما ۱۰ امتیاز گرفتید!»
    try:
        await query.answer(f"🎉 تبریک! شما {REWARD_POINTS} امتیاز گرفتید")
    except Exception as e:
        print(f"❌ خطا در answer کردن دکمه: {e}")

    # ۲) حذف دکمه بعد از استفاده (تا امتیاز تکراری ثبت نشود)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        print(f"ℹ️ حذف دکمه نظر دادم ممکن نشد: {e}")

    # ۳) ثبت امتیاز در دیتابیس (خطای احتمالی مانع ارسال پیام نمی‌شود)
    phone = None
    try:
        phone = get_last_request_phone(user_id)
    except Exception as e:
        print(f"❌ خطا در خواندن شماره آخرین درخواست کاربر: {e}")

    claims_count = None
    try:
        result = save_review_reward(user_id=user_id, phone=phone, branch=branch)
        claims_count = result.get("claims_count") if result else None
    except Exception as e:
        print(f"❌ خطا در ثبت امتیاز نظرسنجی: {e}")

    try:
        log_user_activity(
            query.from_user,
            f"دریافت {REWARD_POINTS} امتیاز هدیه",
            detail=(
                f"شعبه {branch_display_name(branch)}"
                + (f" | تلفن: {phone}" if phone else "")
            ),
        )
    except Exception as e:
        print(f"❌ خطا در ثبت لاگ دریافت امتیاز: {e}")

    # ۴) فقط یک پیام پایانی: تبریک + ۱۰ امتیاز هدیه + بازگشت به منوی اصلی
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=REWARD_CONGRATS_MESSAGE,
            reply_markup=branch_menu_kb(branch, user_id),
        )
    except Exception as e:
        print(f"❌ خطا در ارسال پیام تبریک: {e}")

    # پیشنهاد نشان با ۵۰ امتیاز
    try:
        await send_nshn_offer(context, user_id, branch)
    except Exception as e:
        print(f"❌ خطا در برنامه‌ریزی پیشنهاد نشان: {e}")


async def claim_reward_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """دکمه کیبورد «✅ نظر دادم» بعد از ثبت نظر ۵ ستاره در گوگل مپ"""
    if update.message is None or update.message.text != "✅ نظر دادم":
        return

    user_id = update.effective_user.id
    branch = context.user_data.get("branch", "mashhad")

    # ۱) حذف دکمه کیبورد (بعد از استفاده)
    try:
        await update.message.reply_text(" ", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        print(f"ℹ️ حذف دکمه نظر دادم ممکن نشد: {e}")

    # ۲) ثبت امتیاز در دیتابیس
    phone = None
    try:
        phone = get_last_request_phone(user_id)
    except Exception as e:
        print(f"❌ خطا در خواندن شماره آخرین درخواست کاربر: {e}")

    claims_count = None
    try:
        result = save_review_reward(user_id=user_id, phone=phone, branch=branch)
        claims_count = result.get("claims_count") if result else None
    except Exception as e:
        print(f"❌ خطا در ثبت امتیاز نظرسنجی: {e}")

    try:
        log_user_activity(
            update.effective_user,
            f"دریافت {REWARD_POINTS} امتیاز هدیه",
            detail=(
                f"شعبه {branch_display_name(branch)}"
                + (f" | تلفن: {phone}" if phone else "")
            ),
        )
    except Exception as e:
        print(f"❌ خطا در ثبت لاگ دریافت امتیاز: {e}")

    # ۴) فقط یک پیام پایانی: تبریک + ۱۰ امتیاز هدیه + بازگشت به منوی اصلی
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=REWARD_CONGRATS_MESSAGE,
            reply_markup=branch_menu_kb(branch, user_id),
        )
    except Exception as e:
        print(f"❌ خطا در ارسال پیام تبریک: {e}")

    # پیشنهاد نشان با ۵۰ امتیاز
    try:
        await send_nshn_offer(context, user_id, branch)
    except Exception as e:
        print(f"❌ خطا در برنامه‌ریزی پیشنهاد نشان: {e}")


async def nshn_claim_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the keyboard button user presses after leaving feedback on نشان."""
    if update.message is None or update.message.text != NSHN_BUTTON_TEXT:
        return

    user_id = update.effective_user.id
    branch = context.user_data.get("branch", "mashhad")

    # remove keyboard
    try:
        await update.message.reply_text(" ", reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass

    # register 50-point reward
    try:
        phone = None
        try:
            phone = get_last_request_phone(user_id)
        except Exception:
            phone = None
        result = save_review_reward(user_id=user_id, phone=phone, branch=branch, status="nshn")
        claims_count = result.get("claims_count") if result else None
    except Exception as e:
        print(f"❌ خطا در ثبت امتیاز نشان: {e}")

    try:
        await context.bot.send_message(chat_id=user_id, text=NSHN_REWARD_CONGRATS_MESSAGE, reply_markup=branch_menu_kb(branch, user_id))
    except Exception as e:
        print(f"❌ خطا در ارسال پیام تبریک نشان: {e}")


def user_state(context, user_id):
    """دسترسی به وضعیت (user_data) یک کاربر مشخص

    اگر ادمین از سمت خودش نظرسنجی مشتری را شروع کند، وضعیت باید برای خودِ مشتری
    تنظیم شود؛ پس از application.user_data استفاده میکنیم.
    """
    application = getattr(context, "application", None)
    user_data_map = getattr(application, "user_data", None)
    if user_data_map is not None:
        try:
            return user_data_map[user_id]
        except Exception:
            pass
    return getattr(context, "user_data", {})


def set_survey_step(context, user_id, step=None, **extra):
    """ثبت مرحله نظرسنجی برای یک کاربر"""
    state = user_state(context, user_id)
    if not isinstance(state, dict):
        return

    state["survey_step"] = step
    for key, value in extra.items():
        state[key] = value


def survey_branch_for(context, user_id, fallback="mashhad"):
    """شعبه‌ای که نظرسنجی این کاربر برای آن انجام می‌شود"""
    state = user_state(context, user_id)
    branch = state.get("survey_branch") if isinstance(state, dict) else None
    if not branch:
        branch = context.user_data.get("branch")
    branch = branch or fallback
    return "tehran" if str(branch).lower() == "tehran" else "mashhad"


async def start_survey(context: ContextTypes.DEFAULT_TYPE, user_id: int, branch: str):
    """شروع نظرسنجی رضایت: پرسش امتیاز ۵ ستاره"""
    branch = "tehran" if str(branch).lower() == "tehran" else "mashhad"

    set_survey_step(
        context,
        user_id,
        "five_star",
        survey_branch=branch,
        survey_rating=None,
        survey_id=None,
    )
    await context.bot.send_message(
        chat_id=user_id,
        text=SURVEY_FIVE_STAR_QUESTION,
        reply_markup=ReplyKeyboardMarkup(
            [[BTN_SURVEY_YES], [BTN_SURVEY_NO]], resize_keyboard=True
        ),
        parse_mode="Markdown",
    )


def survey_step_is_answer(step, text):
    """آیا متن ورودی، پاسخ مرحله فعلی نظرسنجی است؟"""
    if step == "five_star":
        return text in SURVEY_YES_TEXTS or text in SURVEY_NO_TEXTS
    if step == "rating_low":
        return text.count("⭐") > 0 or text == BTN_BACK_TEXT
    if step == "low_rating_reason":
        # در این مرحله هر پیامی (شامل «بازگشت») توسط هندلر نظرسنجی بررسی می‌شود
        return True
    return False


async def handle_star_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب امتیاز ۱ تا ۴ ستاره توسط مشتری ناراضی"""
    text = update.message.text
    user_id = update.effective_user.id
    branch = survey_branch_for(context, user_id)

    if text == BTN_BACK_TEXT:
        set_survey_step(context, user_id, None)
        await update.message.reply_text(
            "🔙 به منوی اصلی بازگشتید.",
            reply_markup=branch_menu_kb(branch, user_id),
        )
        return

    rating = text.count("⭐")
    if rating == 0:
        return

    if rating > 4:
        # امتیاز ۵ ستاره فقط از مسیر پرسش اول پذیرفته می‌شود
        await update.message.reply_text(
            LOW_RATING_REQUEST_MESSAGE,
            reply_markup=low_rating_kb(),
            parse_mode="Markdown",
        )
        return

    survey_id = save_survey(user_id, rating, None, branch)

    log_user_activity(
        update.effective_user,
        "ثبت امتیاز زیر ۵ ستاره",
        detail=f"امتیاز {rating} از ۵ | شعبه {branch_display_name(branch)}",
    )

    set_survey_step(
        context,
        user_id,
        "low_rating_reason",
        survey_branch=branch,
        survey_rating=rating,
        survey_id=survey_id,
    )

    await update.message.reply_text(
        f"⭐ امتیاز شما: {rating} از ۵\n\n{LOW_RATING_REASON_REQUEST_MESSAGE}",
        reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
        parse_mode="Markdown",
    )
        return



async def survey_response_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ‌های مشتری به نظرسنجی رضایت (پرسش ۵ ستاره، امتیاز زیر ۵ و دلیل نارضایتی)"""
    user_id = update.effective_user.id
    text = update.message.text
    state = user_state(context, user_id)
    step = state.get("survey_step") if isinstance(state, dict) else None
    branch = survey_branch_for(context, user_id)

    # ===== پاسخ «بله»: اعلام رضایت ۵ ستاره =====
    if step == "five_star" and text in SURVEY_YES_TEXTS:
        # existing flow continues...
        save_survey(user_id, 5, None, branch)

        log_user_activity(
            update.effective_user,
            "اعلام رضایت ۵ ستاره",
            detail=f"شعبه {branch_display_name(branch)}",
        )

        set_survey_step(context, user_id, None, survey_branch=branch)

        # گیف نظرسنجی با دکمه «✅ نظر دادم» ارسال می‌شود
        await send_review_request_messages(context, user_id, branch)
        return

    # ===== پاسخ «خیر»: دریافت امتیاز ۱ تا ۴ ستاره =====
    if text in SURVEY_NO_TEXTS:
        log_user_activity(
            update.effective_user,
            "اعلام نارضایتی",
            detail=f"شعبه {branch_display_name(branch)}",
        )

        set_survey_step(
            context,
            user_id,
            "rating_low",
            survey_branch=branch,
            survey_rating=None,
            survey_id=None,
        )

        await update.message.reply_text(
            LOW_RATING_REQUEST_MESSAGE,
            reply_markup=low_rating_kb(),
            parse_mode="Markdown",
        )
        return

    # ===== مرحله ثبت دلیل نارضایتی =====
    if step == "low_rating_reason":
        if text == BTN_BACK_TEXT:
            set_survey_step(context, user_id, None)
            await update.message.reply_text(
                "🔙 به منوی اصلی بازگشتید.",
                reply_markup=branch_menu_kb(branch, user_id),
            )
            return

        await finish_low_rating_survey(update, context, branch, text)
        return


async def finish_low_rating_survey(update, context, branch, reason):
    """ثبت دلیل نارضایتی روی همان نظرسنجی و ارسال آن به گروه نارضایتی شعبه"""
    user_id = update.effective_user.id
    state = user_state(context, user_id)
    state = state if isinstance(state, dict) else {}

    rating = state.get("survey_rating") or 0
    survey_id = state.get("survey_id")

    if survey_id:
        update_survey_comment(survey_id, reason)
    else:
        survey_id = save_survey(user_id, rating, reason, branch)

    log_user_activity(
        update.effective_user,
        "ثبت دلیل نارضایتی",
        detail=(
            f"امتیاز {rating if rating else 'بدون امتیاز'} | "
            f"شعبه {branch_display_name(branch)}"
        ),
    )

    complaint_group = (
        GROUP_MASHHAD_COMPLAINT if branch == "mashhad" else GROUP_TEHRAN_COMPLAINT
    )

    # شماره‌ای که کاربر برای دریافت عکس وارد کرده است
    request_phone = None
    try:
        request_phone = get_last_request_phone(user_id)
    except Exception as e:
        print(f"❌ خطا در خواندن شماره آخرین درخواست کاربر: {e}")

    try:
        await context.bot.send_message(
            chat_id=complaint_group,
            text=(
                "📝 نارضایتی جدید\n\n"
                f"👤 کاربر: {getattr(update.effective_user, 'first_name', None) or 'کاربر بدون نام'}\n"
                f"🆔 آیدی: {user_id}\n"
                f"📱 شماره: {request_phone if request_phone else 'نامشخص'}\n"
                f"📍 شعبه: {branch_display_name(branch)}\n"
                f"⭐ امتیاز: {rating if rating else 'بدون امتیاز'}\n"
                f"📝 پیام:\n{reason}"
            ),
        )
    except Exception as e:
        print(f"❌ خطا در ارسال به گروه نارضایتی: {e}")

    set_survey_step(context, user_id, None)

    await update.message.reply_text(
        LOW_RATING_THANKS_MESSAGE,
        reply_markup=branch_menu_kb(branch, user_id),
        parse_mode="Markdown",
    )


def save_survey(user_id, rating, comment, branch):
    """ذخیره نظرسنجی در دیتابیس با شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO surveys (user_id, rating, comment, branch, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (user_id, rating, comment, branch),
        )
        conn.commit()
        return c.lastrowid
    except Exception as e:
        print(f"❌ خطا در ذخیره نظرسنجی: {e}")
        return None
    finally:
        conn.close()


async def start(update, context):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر گرامی"

    log_user_activity(update.effective_user, "شروع ربات (/start)")

    if not await real_member(context, user_id):
        msg = await update.message.reply_text(
            f"سلام {user_name} عزیز!\n\n"
            "به ربات پسران کریم خوش آمدید🌹\n\n"
            "برای استفاده از ربات، ابتدا در کانال رسمی رستوران پسران کریم عضو شوید🙏\n\n"
            "پس از عضویت، دکمه‌ی بررسی عضویت را بزنید.",
            reply_markup=membership_kb(),
            parse_mode="Markdown",
        )
        context.user_data["start_message_id"] = msg.message_id
        return

    if "branch" in context.user_data:
        branch = context.user_data["branch"]

        if branch == "mashhad":
            reply_markup = mashhad_menu_kb(user_id)
        else:
            reply_markup = tehran_menu_kb(user_id)

        msg = await update.message.reply_text(
            f"سلام {user_name} عزیز!\n\n"
            "به ربات رستوران پسران کریم خوش آمدید🌹\n\n"
            "لطفا شعبه مورد نظر خود را انتخاب کنید 👇",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
        context.user_data["start_message_id"] = msg.message_id
    else:
        msg = await update.message.reply_text(
            f"سلام {user_name} عزیز!\n\n"
            "به ربات رستوران پسران کریم خوش آمدید🌹\n\n"
            "لطفا شعبه مورد نظر خود را انتخاب کنید 👇",
            reply_markup=branch_kb(),
            parse_mode="Markdown",
        )
        context.user_data["start_message_id"] = msg.message_id


async def check_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name or "کاربر گرامی"

    if await real_member(context, user_id):
        log_user_activity(query.from_user, "بررسی عضویت در کانال (تایید شد)")
        await query.delete_message()

        await context.bot.send_message(
            chat_id=user_id,
            text=f"عضویت شما تایید شد✅\n\n" "لطفا شعبه مورد نظر خود را انتخاب کنید👇",
            reply_markup=branch_kb(),
            parse_mode="Markdown",
        )
    else:
        await query.answer(
            "شما هنوز عضو کانال نشدید❌ لطفا ابتدا عضو شوید.", show_alert=True
        )


async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای پاسخ ادمین به سوال عکس بعدی"""
    text = update.message.text

    if "admin_upload" not in context.user_data:
        return

    admin_data = context.user_data["admin_upload"]
    phone = admin_data["phone"]
    photo_code = admin_data["photo_code"]
    branch = admin_data["branch"]
    customer_user_id = admin_data["user_id"]
    count = admin_data.get("count", 1)

    if text == "بله، عکس دیگری دارم":
        await update.message.reply_text(
            "📸 لطفا عکس بعدی را ارسال کنید.\n\n"
            f"📱 شماره: {phone}\n"
            f"🏷️ کد: {photo_code}\n\n"
            "✅ بدون نیاز به کپشن، فقط عکس را بفرستید.",
            reply_markup=ReplyKeyboardMarkup([[BTN_NO]], resize_keyboard=True),
        )

        context.user_data["admin_upload"]["step"] = "waiting_for_photo"
        return

    elif text == "نه، تمام شد":
        context.user_data.pop("admin_upload", None)

        finished_text = (
            f"✅ همه عکس‌ها ارسال شدند.\n\n"
            f"📱 شماره: {phone}\n"
            f"🏷️ کد: {photo_code}\n"
            f"📸 تعداد عکس‌های ارسال‌شده: {count}"
        )

        # در گروه‌های کاری، پنل مدیریت فرستاده نمی‌شود و کیبورد گیرکرده
        # بله/خیر از صفحه ادمین پاک می‌شود تا دکمه‌ها بی‌اثر نمانند
        chat_type = getattr(getattr(update, "effective_chat", None), "type", "private")
        if chat_type and chat_type != "private":
            await update.message.reply_text(
                finished_text + "\n\n🔙 برای ادامه در ربات خصوصی پیام بدهید.",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                finished_text,
                reply_markup=admin_panel_kb(),
                parse_mode="Markdown",
            )

        # پیام تحویل عکس حالا داخل کپشن خود عکس است؛ مستقیم نظرسنجی شروع می‌شود
        await start_survey(context, customer_user_id, branch)
        return

    if context.user_data.get("admin_upload", {}).get("step") == "waiting_for_photo":
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            is_photo = True
        elif update.message.document:
            file_id = update.message.document.file_id
            is_photo = False
        else:
            await update.message.reply_text("❌ لطفا یک عکس یا فایل بفرستید.")
            return

        try:
            if is_photo:
                await context.bot.send_photo(
                    chat_id=customer_user_id,
                    photo=file_id,
                    caption=PHOTO_DELIVERED_MESSAGE,
                    parse_mode="Markdown",
                )
            else:
                await context.bot.send_document(
                    chat_id=customer_user_id,
                    document=file_id,
                    caption=PHOTO_DELIVERED_MESSAGE,
                    parse_mode="Markdown",
                )

            # این درخواست ارسال شد؛ از لیست انتظار گروه شعبه حذف می‌شود
            mark_request_as_sent(phone, photo_code, branch)

            context.user_data["admin_upload"]["count"] = (
                context.user_data["admin_upload"].get("count", 1) + 1
            )

            await update.message.reply_text(
                f"✅ عکس شماره {context.user_data['admin_upload']['count']} ارسال شد."
            )

            keyboard = ReplyKeyboardMarkup([[BTN_YES], [BTN_NO]], resize_keyboard=True)

            await update.message.reply_text(
                "آیا عکس دیگری برای این مشتری دارید؟\n\n"
                f"📱 شماره: {phone}\n"
                f"🏷️ کد: {photo_code}\n"
                f"📸 ارسال‌شده: {context.user_data['admin_upload']['count']} عکس",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

            context.user_data["admin_upload"]["step"] = "asking"

        except Exception as e:
            await update.message.reply_text(f"❌ ارسال ناموفق! خطا: {e}")


async def handle_photo_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ ادمین به پرسش «عکس دیگری دارید؟» در گروه‌های عکس

    بدون این هندلر، دکمه‌های «بله، عکس دیگری دارم» و «نه، تمام شد» در گروه کاری
    بی‌اثر می‌ماندند و نظرسنجی مشتری شروع نمی‌شد.
    """
    text = update.message.text
    if text not in (BTN_YES.text, BTN_NO.text):
        return

    if not context.user_data.get("admin_upload"):
        return

    await handle_admin_response(update, context)


async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر گرامی"

    log_user_activity(update.effective_user, "درخواست پشتیبانی")

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🟡 ارتباط با پشتیبانی 🟡",
                    url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}",
                )
            ],
        ]
    )

    await update.message.reply_text(
        "برای ارتباط با پشتیبانی و دریافت راهنمایی، روی دکمه زیر کلیک کنید:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_all_messages(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if not await real_member(context, user_id):
        try:
            if "start_message_id" in context.user_data:
                await context.bot.delete_message(
                    chat_id=user_id, message_id=context.user_data["start_message_id"]
                )
        except:
            pass

        msg = await update.message.reply_text(
            "❌ شما از کانال خارج شدید!\n\n"
            "برای استفاده مجدد از ربات، لطفا در کانال رسمی رستوران پسران کریم عضو شوید.\n\n"
            "پس از عضویت، دوباره روی دکمه‌ی بررسی عضویت کلیک کنید..",
            reply_markup=membership_kb(),
            parse_mode="Markdown",
        )
        context.user_data["start_message_id"] = msg.message_id
        return

    # ===== ثبت لاگ استفاده از ربات (چه کسی، چه زمانی و با چه تاریخ عضویتی) =====
    log_user_activity(
        update.effective_user,
        build_usage_action(text, context.user_data.get("photo_step")),
        detail=(
            f"شعبه: {'مشهد' if context.user_data.get('branch') == 'mashhad' else 'تهران'}"
            if context.user_data.get("branch")
            else None
        ),
    )

    if text in ["بله، عکس دیگری دارم", "نه، تمام شد"] and context.user_data.get(
        "admin_upload"
    ):
        await handle_admin_response(update, context)
        return

    photo_step = context.user_data.get("photo_step")
    if text == BTN_BACK_TEXT and photo_step in [
        "year",
        "month",
        "day",
        "code",
        "phone",
    ]:
        if photo_step == "phone":
            context.user_data["photo_step"] = "code"
            await update.message.reply_text(
                "🔙 به بخش وارد کردن کد عکس بازگشتید.\n"
                "لطفا کد 4 رقمی عکس را وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
                parse_mode="Markdown",
            )
        elif photo_step == "code":
            context.user_data["photo_step"] = "day"
            year = context.user_data.get("photo_year", 1404)
            month = context.user_data.get("photo_month", 1)
            await update.message.reply_text(
                "🔙 به انتخاب روز بازگشتید.\n\n"
                "لطفا روزی که در آن عکس گرفته اید را انتخاب کنید:",
                reply_markup=day_kb(year, month),
                parse_mode="Markdown",
            )
        elif photo_step == "day":
            context.user_data["photo_step"] = "month"
            year = context.user_data.get("photo_year", 1404)
            await update.message.reply_text(
                "🔙 به انتخاب ماه بازگشتید.\n\n"
                "لطفا ماه مورد نظر که در آن عکس گرفتید را انتخاب کنید:",
                reply_markup=month_kb(year),
                parse_mode="Markdown",
            )
        elif photo_step == "month":
            context.user_data["photo_step"] = "year"
            await update.message.reply_text(
                "🔙 به انتخاب سال بازگشتید.\n\n"
                "لطفا سالی که عکس را گرفته‌اید انتخاب کنید:",
                reply_markup=year_kb(),
                parse_mode="Markdown",
            )
        else:
            context.user_data["photo_step"] = None
            branch = context.user_data.get("branch", "mashhad")
            await update.message.reply_text(
                "🔙 به منوی اصلی بازگشتید.",
                reply_markup=branch_menu_kb(branch, user_id),
            )
        return

    if text == "شعبه مشهد(خیام)":
        context.user_data["branch"] = "mashhad"
        await update.message.reply_text(
            "شعبه مشهد (خیام) انتخاب شد✅\n\n"
            "برای استفاده یکی از گزینه های زیر را انتخاب کنید👇:",
            reply_markup=branch_menu_kb("mashhad", user_id),
            parse_mode="Markdown",
        )
        return

    elif text == "شعبه تهران(هتل پارسیان آزادی)":
        context.user_data["branch"] = "tehran"
        await update.message.reply_text(
            "شعبه تهران (هتل پارسیان آزادی) انتخاب شد✅\n\n"
            "برای استفاده یکی از گزینه های زیر را انتخاب کنید👇",
            reply_markup=branch_menu_kb("tehran", user_id),
            parse_mode="Markdown",
        )
        return

    elif text == BTN_SUPPORT.text:
        await support_handler(update, context)
        return

    elif text == "تغییر شعبه":
        context.user_data["branch"] = None
        await update.message.reply_text(
            "لطفا شعبه مورد نظر خود را انتخاب کنید👇",
            reply_markup=branch_kb(),
            parse_mode="Markdown",
        )
        return

    survey_state = user_state(context, user_id)
    survey_step = (
        survey_state.get("survey_step") if isinstance(survey_state, dict) else None
    )

    if survey_step_is_answer(survey_step, text):
        if survey_step == "rating_low":
            await handle_star_selection(update, context)
        else:
            await survey_response_handler(update, context)
        return

    if text == "🛠️ پنل مدیریت":
        await admin_command(update, context)
        return

    elif text == "آمار":
        await admin_stats(update, context)
        return

    elif text == "📋 کاربران ربات":
        await admin_users_log(update, context)
        return

    elif text == "🧾 لاگ استفاده از ربات":
        await admin_usage_log(update, context)
        return

    elif text == "📤 ارسال لیست انتظار":
        await admin_send_waiting_list(update, context)
        return

    elif text == BTN_ADMIN_REWARD_CLAIMS.text:
        await admin_reward_claims(update, context)
        return

    elif text == BTN_ADMIN_REVIEW_GIF.text:
        await admin_review_gif(update, context)
        return

    elif text in REVIEW_GIF_SET_TEXTS or text in REVIEW_GIF_DELETE_TEXTS:
        await handle_review_gif_choice(update, context)
        return

    elif context.user_data.get("admin_action") == "review_gif":
        await update.message.reply_text(
            "🎬 لطفا گیف یا ویدیوی مورد نظر را ارسال کنید.\n\n"
            "برای انصراف دکمه «بازگشت به منو» را بزنید.",
            reply_markup=ReplyKeyboardMarkup([[BTN_ADMIN_BACK]], resize_keyboard=True),
        )
        return

    elif text == "⏳ در انتظار - مشهد":
        await admin_pending_branch(update, context, "mashhad")
        return

    elif text == "⏳ در انتظار - تهران":
        await admin_pending_branch(update, context, "tehran")
        return

    elif text == "❌ ارسال ناموفق - مشهد":
        await admin_failed_branch(update, context, "mashhad")
        return

    elif text == "❌ ارسال ناموفق - تهران":
        await admin_failed_branch(update, context, "tehran")
        return

    elif text == "ارسال مجدد":
        await admin_resend(update, context)
        return

    elif text == "👥 مدیریت ادمین‌ها":
        await admin_manage(update, context)
        return

    elif text == "➕ افزودن ادمین":
        await admin_add(update, context)
        return

    elif text == "➖ حذف ادمین":
        await admin_remove(update, context)
        return

    elif text == "📋 لیست ادمین‌ها":
        await admin_list(update, context)
        return

    elif context.user_data.get("admin_action") == "preupload":
        await admin_preupload_phone_code(update, context)
        return

    elif context.user_data.get("admin_action") in ["add_admin", "remove_admin"]:
        await handle_admin_management(update, context)
        return

    elif text == "🔙 بازگشت به منو":
        context.user_data["in_admin_panel"] = False

        # اگر ادمین وسط ثبت گیف نظرسنجی منصرف شد، حالت انتظار پاک می‌شود
        if context.user_data.get("admin_action") == "review_gif":
            context.user_data.pop("admin_action", None)
            context.user_data.pop("review_gif_branch", None)

        branch = context.user_data.get("branch", "mashhad")
        await update.message.reply_text(
            "🔙 به منوی اصلی بازگشتید.",
            reply_markup=branch_menu_kb(branch, user_id),
            parse_mode="Markdown",
        )
        return

    branch = context.user_data.get("branch", "mashhad")

    if context.user_data.get("photo_step") == "phone":
        if text == BTN_BACK_TEXT:
            context.user_data["photo_step"] = "code"
            await update.message.reply_text(
                "🔙 به بخش وارد کردن کد عکس بازگشتید.\n"
                "لطفا کد 4 رقمی عکس را وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
                parse_mode="Markdown",
            )
            return

        phone = normalize_phone_number(text)
        if is_valid_phone_number(phone):
            context.user_data["photo_phone"] = phone
            context.user_data["photo_step"] = "complete"
            photo_branch = context.user_data.get("photo_branch", "mashhad")
            photo_code = context.user_data.get("photo_code")
            photo_date = context.user_data.get("photo_date")

            preuploaded = get_preuploaded_photo(phone, photo_code, photo_branch)
            if preuploaded:
                preupload_id, file_id, file_type, message_id, created_at = preuploaded
                try:
                    await send_preuploaded_file(
                        context=context,
                        chat_id=user_id,
                        file_id=file_id,
                        file_type=file_type,
                    )
                    mark_preuploaded_as_used(preupload_id)
                    save_photo_request(
                        user_id=user_id,
                        phone=phone,
                        photo_code=photo_code,
                        photo_date=photo_date,
                        branch=photo_branch,
                        status="sent",
                    )
                    await handle_new_photo_request(
                        context,
                        update.effective_user,
                        photo_branch,
                        phone,
                        photo_code,
                        photo_date,
                        photo_sent=True,
                    )
                    await start_survey(context, user_id, photo_branch)
                    context.user_data["photo_step"] = None
                    return
                except Exception as e:
                    print(f"❌ خطا در ارسال عکس پیش‌آپلود: {e}")

            save_photo_request(
                user_id=user_id,
                phone=phone,
                photo_code=photo_code,
                photo_date=photo_date,
                branch=photo_branch,
            )
            await handle_new_photo_request(
                context,
                update.effective_user,
                photo_branch,
                phone,
                photo_code,
                photo_date,
            )
            await update.message.reply_text(
                "درخواست شما ثبت شد✅\n\n"
                "شما در صف انتظار هستید و به محض آماده شدن عکس، فایل آن برای شما ارسال میشود.",
                reply_markup=branch_menu_kb(photo_branch, user_id),
                parse_mode="Markdown",
            )
            context.user_data["photo_step"] = None
            return

        await update.message.reply_text(
            "❌ شماره تلفن وارد شده معتبر نیست!\n\n"
            "لطفا یک شماره 11 رقمی که با 09 شروع میشود وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
        )
        return

    if branch == "mashhad":
        if text == "دریافت عکس یادگاری":
            context.user_data["photo_branch"] = branch
            context.user_data["photo_step"] = "year"
            await update.message.reply_text(
                f"📍 شما در شعبه مشهد (خیام) هستید.\n\n"
                "🔹 لطفا سالی که عکس را گرفته‌اید انتخاب کنید:",
                reply_markup=year_kb(),
                parse_mode="Markdown",
            )
            return

        elif text == "اپلیکیشن پسران کریم":
            if branch == "mashhad":
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟡 دانلود اپلیکیشن پسران کریم 🟡",
                                url="www.pesaranekarim.rest/app",
                            )
                        ]
                    ]
                )
                await update.message.reply_text(
                    "لطفا جهت دانلود اپلیکیشن رستوران پسران کریم روی دکمه زیر کلیک فرمایید:\n\n\n\n",
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

        elif text == "منو به همراه قیمت":
            if branch == "mashhad":
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟡 مشاهده منو به همراه قیمت 🟡",
                                url="https://www.pesaranekarim.rest/menu-mashhad",
                            )
                        ]
                    ]
                )
                await update.message.reply_text(
                    "لطفا جهت مشاهده منو رستوران پسران کریم مشهد به همراه قیمت، روی دکمه زیر کلیک فرمایید:",
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

        elif text == "منو به همراه تصویر":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟡 مشاهده منو به همراه تصاویر 🟡",
                            url="https://www.pesaranekarim.rest/menu",
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                "برای مشاهده منو به همراه تصاویر و توضیحات روی دکمه زیر کلیک کنید:",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        elif text == "سفارش آنلاین":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟡 سفارش آنلاین 🟡", url="www.pesaranekarim.rest"
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                "لطفا جهت سفارش آنلاین، روی دکمه زیر کلیک فرمایید:\n\n",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        elif text == "سفارش تلفنی و رزرو مجالس":
            await update.message.reply_text(
                "تلفن های ما جهت سفارش و ارسال غذا و رزرو مجالس:\n\n"
                "🟡 05131919\n\n"
                "🟡 05137530013\n\n"
                "🟡 05137530014\n\n"
                "🟡 05137530015",
                parse_mode="Markdown",
            )

        elif text == "مسیریابی(لوکیشن)":
            if branch == "mashhad":
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟡 مسیریابی به رستوران پسران کریم خیام",
                                url="https://www.pesaranekarim.rest/direction/mashhad",
                            )
                        ]
                    ]
                )
                await update.message.reply_text(
                    "لطفا جهت مسیریابی به رستوران پسران کریم خیام، روی دکمه زیر کلیک فرمایید",
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

        elif text == "آدرس ما":
            if branch == "mashhad":
                await update.message.reply_text(
                    "🟡 آدرس ما:\n\n 🟡"
                    "مشهد: بلوار خیام به سمت الماس شرق، بین خیام 61و63، ساختمان مروارید، طبقه منفی ۲، رستوران پسران کریم",
                    parse_mode="Markdown",
                )

        elif text == "شبکه های اجتماعی ما":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔍 وبسایت رسمی", url="https://www.pesaranekarim.rest"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📷 اینستاگرام", url="https://instagram.com/pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💬 ایکس (توییتر سابق)",
                            url="X.com/pesaranekarim",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🅰️ تردز", url="https://threads.net/@pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 تیکتاک", url="https://tiktok.com/@pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💬 فیسبوک", url="https://facebook.com/pesaranekarim.rest"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔵 لینکدین",
                            url="https://linkedin.com/company/pesaranekarim/",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💬 کانال تلگرام", url="https://t.me/pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💻 ربات تلگرام", url="https://t.me/pesaranekarimbot"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔴 کانال آپارات", url="https://aparat.com/pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📺 کانال یوتیوب", url="https://youtube.com/@pesaranekarim"
                        )
                    ],
                ]
            )

            await update.message.reply_text(
                "برای مشاهده هر بخش روی دکمه مربوطه کلیک کنید:",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        elif text == "تاریخچه پسران کریم":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟡 تاریخچه پسران کریم 🟡",
                            url="https://www.pesaranekarim.rest/history",
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                "برای مشاهده تاریخچه روی دکمه زیر کلیک کنید:",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

    else:
        if text == "دریافت عکس یادگاری":
            context.user_data["photo_branch"] = branch
            context.user_data["photo_step"] = "year"
            await update.message.reply_text(
                "📍 شما در شعبه تهران (هتل پارسیان آزادی) هستید.\n\n"
                "با سلام و احترام\n"
                "وقتتون بخیر\n\n"
                "لطفا مرحمت فرمایید کد عکس، تاریخ و شماره تماسی که در پشت برگه یادداشت شده را ارسال فرمایید:\n\n"
                "🔹 لطفا سالی که عکس را گرفته‌اید انتخاب کنید:",
                reply_markup=year_kb(),
                parse_mode="Markdown",
            )
            return

        elif text == "اپلیکیشن پسران کریم":
            if branch == "tehran":
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟡 دانلود اپلیکیشن پسران کریم 🟡",
                                url="www.pesaranekarim.rest/app",
                            )
                        ]
                    ]
                )
                await update.message.reply_text(
                    "لطفا جهت دانلود اپلیکیشن رستوران پسران کریم روی دکمه زیر کلیک فرمایید:\n\n\n\n",
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

        elif text == "منو به همراه قیمت":
            if branch == "tehran":
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟡 مشاهده منو به همراه قیمت 🟡",
                                url="https://www.pesaranekarim.rest/menu-tehran",
                            )
                        ]
                    ]
                )
                await update.message.reply_text(
                    "لطفا جهت مشاهده منو رستوران پسران کریم تهران به همراه قیمت، روی دکمه زیر کلیک فرمایید:\n\n",
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

        elif text == "منو به همراه تصویر":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟡 مشاهده منو به همراه تصویر 🟡",
                            url="https://www.pesaranekarim.rest/menu",
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                "برای مشاهده منو به همراه تضاویر و توضیحات روی دکمه زیر کلیک کنید:",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        elif text == "سفارش آنلاین":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟡 سفارش آنلاین 🟡", url="www.pesaranekarim.rest"
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                "لطفا جهت سفارش آنلاین، روی دکمه زیر کلیک فرمایید:\n\n",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        elif text == "سفارش تلفنی و رزرو مجالس":
            await update.message.reply_text(
                "تلفن های ما جهت سفارش و ارسال غذا و رزرو مجالس:\n\n"
                "🟡 05131919\n\n"
                "🟡 02122344513\n\n"
                "🟡 02129117603\n\n"
                "(از تلفن ثابت) داخلی اتاق هتل پارسیان آزادی\n\n"
                "2603",
                parse_mode="Markdown",
            )

        elif text == "مسیریابی(لوکیشن)":
            if branch == "tehran":
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟡 مسیریابی به رستوران پسران کریم تهران 🟡",
                                url="https://www.pesaranekarim.rest/direction/tehran",
                            )
                        ]
                    ]
                )
                await update.message.reply_text(
                    "لطفا جهت مسیریابی به رستوران پسران کریم تهران (هتل پارسیان)، روی دکمه زیر کلیک فرمایید:",
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

        elif text == "آدرس ما":
            if branch == "tehran":
                await update.message.reply_text(
                    "🟡 آدرس ما:\n\n"
                    "تقاطع بزرگراه چمران و یادگار امام، هتل پارسیان آزادی، طبقه 26، رستوران پسران کریم",
                    parse_mode="Markdown",
                )

        elif text == "شبکه های اجتماعی ما":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔍 وبسایت رسمی", url="https://www.pesaranekarim.rest"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📷 اینستاگرام",
                            url="https://instagram.com/pesaranekarimtehran",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💬 ایکس (توییتر سابق)",
                            url="X.com/pesaranekarim",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🅰️ تردز", url="https://threads.net/@pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 تیکتاک", url="https://tiktok.com/@pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💬 فیسبوک", url="https://facebook.com/pesaranekarim.rest"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔵 لینکدین",
                            url="https://linkedin.com/company/pesaranekarim/",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💬 کانال تلگرام", url="https://t.me/pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💻 ربات تلگرام", url="https://t.me/pesaranekarimbot"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔴 کانال آپارات", url="https://aparat.com/pesaranekarim"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📺 کانال یوتیوب", url="https://youtube.com/@pesaranekarim"
                        )
                    ],
                ]
            )

            await update.message.reply_text(
                "برای مشاهده هر بخش روی دکمه مربوطه کلیک کنید:",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        elif text == "تاریخچه پسران کریم":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟡 تاریخچه پسران کریم 🟡",
                            url="https://www.pesaranekarim.rest/history",
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                "برای مشاهده تاریخچه روی دکمه زیر کلیک کنید:",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

    if text in get_persian_years() and context.user_data.get("photo_step") == "year":
        context.user_data["photo_year"] = int(text)
        context.user_data["photo_step"] = "month"
        await update.message.reply_text(
            f"سال {text} انتخاب شد✅\n\n"
            "لطفا ماه مورد نظر که در آن عکس گرفتید را انتخاب کنید:",
            reply_markup=month_kb(int(text)),
            parse_mode="Markdown",
        )
        return

    if text in MONTHS and context.user_data.get("photo_step") == "month":
        month_index = MONTHS.index(text) + 1
        year = context.user_data.get("photo_year", 1404)
        if month_index > get_max_month_for_year(year):
            await update.message.reply_text(
                "❌ این ماه هنوز فرا نرسیده است. لطفا ماه دیگری انتخاب کنید:",
                reply_markup=month_kb(year),
            )
            return

        context.user_data["photo_month"] = month_index
        context.user_data["photo_step"] = "day"

        await update.message.reply_text(
            f"ماه {text} انتخاب شد✅\n\n"
            "لطفا روزی که در آن عکس گرفته اید را انتخاب کنید:",
            reply_markup=day_kb(year, month_index),
            parse_mode="Markdown",
        )
        return

    if (
        text.isdigit()
        and len(text) <= 2
        and context.user_data.get("photo_step") == "day"
    ):
        day = int(text)
        year = context.user_data.get("photo_year", 1404)
        month = context.user_data.get("photo_month", 1)

        max_days = get_max_day_for_month(year, month)

        if 1 <= day <= max_days:
            context.user_data["photo_day"] = day
            context.user_data["photo_step"] = "code"

            date_str = f"{year}/{month:02d}/{day:02d}"
            context.user_data["photo_date"] = date_str

            await update.message.reply_text(
                f"تاریخ {year}/{month:02d}/{day:02d} ثبت شد✅\n\n"
                "لطفا کد 4 رقمی عکس خود را وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"❌ روز {day} برای این ماه معتبر نیست.\n"
                f"لطفا عددی بین 1 تا {max_days} وارد کنید:",
                reply_markup=day_kb(year, month),
            )
        return

    if context.user_data.get("photo_step") == "code":
        code = normalize_photo_code(text)
        if code.isdigit() and len(code) == 4:
            context.user_data["photo_code"] = code
            context.user_data["photo_step"] = "phone"
            await update.message.reply_text(
                f"کد عکس {code} ثبت شد✅\n\n"
                "لطفا شماره تلفن 11 رقمی خود را وارد کنید:\n"
                "(مثلا 09123456789 یا ۰۹۱۲۳۴۵۶۷۸۹)",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ کد وارد شده معتبر نیست!\n" "لطفا یک کد 4 رقمی وارد کنید",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
            )
        return

    if context.user_data.get("photo_step") == "phone":
        if text == BTN_BACK_TEXT:
            context.user_data["photo_step"] = "code"
            await update.message.reply_text(
                "🔙 به بخش وارد کردن کد عکس بازگشتید.\n"
                "لطفا کد 4 رقمی عکس را وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
                parse_mode="Markdown",
            )
            return

        phone = normalize_phone_number(text)
        if is_valid_phone_number(phone):
            context.user_data["photo_phone"] = phone
            context.user_data["photo_step"] = "complete"

            photo_branch = context.user_data.get("photo_branch", "mashhad")
            photo_code = context.user_data.get("photo_code")
            photo_date = context.user_data.get("photo_date")

            preuploaded = get_preuploaded_photo(phone, photo_code, photo_branch)

            if preuploaded:
                preupload_id, file_id, file_type, message_id, created_at = preuploaded

                try:
                    await send_preuploaded_file(
                        context=context,
                        chat_id=user_id,
                        file_id=file_id,
                        file_type=file_type,
                    )

                    mark_preuploaded_as_used(preupload_id)

                    save_photo_request(
                        user_id=user_id,
                        phone=phone,
                        photo_code=photo_code,
                        photo_date=photo_date,
                        branch=photo_branch,
                        status="sent",
                    )

                    await handle_new_photo_request(
                        context,
                        update.effective_user,
                        photo_branch,
                        phone,
                        photo_code,
                        photo_date,
                        photo_sent=True,
                    )

                    await start_survey(context, user_id, photo_branch)
                    context.user_data["photo_step"] = None
                    return

                except Exception as e:
                    print(f"❌ خطا در ارسال عکس پیش‌آپلود: {e}")

            save_photo_request(
                user_id=user_id,
                phone=phone,
                photo_code=photo_code,
                photo_date=photo_date,
                branch=photo_branch,
            )

            await handle_new_photo_request(
                context,
                update.effective_user,
                photo_branch,
                phone,
                photo_code,
                photo_date,
            )

            await update.message.reply_text(
                "درخواست شما ثبت شد✅\n\n"
                "شما در صف انتظار هستید و به محض آماده شدن عکس، فایل آن برای شما ارسال میشود.",
                reply_markup=branch_menu_kb(photo_branch, user_id),
                parse_mode="Markdown",
            )

            context.user_data["photo_step"] = None

        else:
            await update.message.reply_text(
                "❌ شماره تلفن وارد شده معتبر نیست!\n\n"
                "لطفا یک شماره 11 رقمی که با 09 شروع میشود وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
            )
        return

    if text == BTN_BACK_TEXT:
        await update.message.reply_text(
            "🔙 به منوی اصلی بازگشتید.",
            reply_markup=branch_menu_kb(branch, user_id),
        )
        return


async def handle_group_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.message.chat_id
    if chat_id not in [GROUP_MASHHAD_PHOTO, GROUP_TEHRAN_PHOTO]:
        return

    # ✅ در گروه‌های عکس، همه اعضا می‌توانند عکس بفرستند و پیام «دسترسی ندارید» داده نمی‌شود.
    # برای محدود کردن دوباره به ادمین‌ها، مقدار ALLOW_GROUP_PHOTOS_FOR_ALL را
    # در فایل config.py روی False بگذارید.
    sender_is_admin = is_admin(update.effective_user.id)
    if not sender_is_admin and not ALLOW_GROUP_PHOTOS_FOR_ALL:
        await update.message.reply_text("شما دسترسی به این بخش ندارید❌")
        return

    branch = "mashhad" if chat_id == GROUP_MASHHAD_PHOTO else "tehran"

    if context.user_data.get("admin_action") == "preupload_photo":
        phone = context.user_data.get("preupload_phone")
        photo_code = context.user_data.get("preupload_code")
        admin_id = update.effective_user.id

        if not phone or not photo_code:
            await update.message.reply_text(
                "❌ شماره و کد ثبت نشده! لطفاً دوباره تلاش کنید."
            )
            context.user_data.pop("admin_action", None)
            return

        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
        elif update.message.document:
            file_id = update.message.document.file_id
            file_type = "document"
        else:
            await update.message.reply_text("❌ لطفا یک عکس یا فایل بفرستید.")
            return

        result = save_preuploaded_photo(
            phone=phone,
            photo_code=photo_code,
            branch=branch,
            file_id=file_id,
            admin_id=admin_id,
            message_id=update.message.message_id,
            file_type=file_type,
        )

        if result:
            await update.message.reply_text(
                f"✅ عکس ذخیره شد و آماده‌ی ارسال در زمان درخواست مشتری است.\n\n"
                f"📱 شماره: `{phone}`\n"
                f"🏷️ کد: `{photo_code}`\n"
                f"📍 شعبه: {'مشهد' if branch == 'mashhad' else 'تهران'}\n\n"
                "🔹 وقتی مشتری درخواست عکس را ثبت کرد، این تصویر برای او ارسال خواهد شد.",
                parse_mode="Markdown",
                reply_markup=admin_panel_kb(),
            )
        else:
            await update.message.reply_text(
                "❌ خطا در ذخیره عکس. لطفا دوباره تلاش کنید."
            )

        context.user_data.pop("admin_action", None)
        context.user_data.pop("preupload_phone", None)
        context.user_data.pop("preupload_code", None)
        return

    if context.user_data.get("admin_upload", {}).get("step") == "waiting_for_photo":
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            is_photo = True
        elif update.message.document:
            file_id = update.message.document.file_id
            is_photo = False
        else:
            await update.message.reply_text("❌ لطفا یک عکس یا فایل بفرستید.")
            return

        admin_data = context.user_data["admin_upload"]
        phone = admin_data["phone"]
        photo_code = admin_data["photo_code"]
        customer_user_id = admin_data["user_id"]

        try:
            if is_photo:
                await context.bot.send_photo(
                    chat_id=customer_user_id,
                    photo=file_id,
                    caption=f"📸 عکس یادگاری شما\n\n"
                    "از اینکه رستوران پسران کریم را انتخاب کردید سپاسگذاریم🌹",
                    parse_mode="Markdown",
                )
            else:
                await context.bot.send_document(
                    chat_id=customer_user_id,
                    document=file_id,
                    caption=f"📸 عکس یادگاری شما\n\n"
                    "از اینکه رستوران پسران کریم را انتخاب کردید سپاسگذاریم🌹",
                    parse_mode="Markdown",
                )

            # این درخواست ارسال شد؛ از لیست انتظار گروه شعبه حذف می‌شود
            mark_request_as_sent(phone, photo_code, branch)

            context.user_data["admin_upload"]["count"] = (
                context.user_data["admin_upload"].get("count", 1) + 1
            )

            await update.message.reply_text(
                f"✅ عکس شماره {context.user_data['admin_upload']['count']} ارسال شد."
            )

            keyboard = ReplyKeyboardMarkup([[BTN_YES], [BTN_NO]], resize_keyboard=True)

            await update.message.reply_text(
                "📸 آیا عکس دیگری برای این مشتری دارید؟\n\n"
                f"📱 شماره: {phone}\n"
                f"🏷️ کد: {photo_code}\n"
                f"📸 ارسال‌شده: {context.user_data['admin_upload']['count']} عکس",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

            context.user_data["admin_upload"]["step"] = "asking"

        except Exception as e:
            await update.message.reply_text(f"❌ ارسال ناموفق! خطا: {e}")
        return

    caption = (update.message.caption or "").strip()

    # عکس بدون کپشن در گروه کاری: پاسخی داده نمی‌شود تا مزاحم اعضای گروه نشویم
    if not caption:
        return

    phone, photo_code = extract_phone_and_code(caption)

    if not (phone.isdigit() and len(phone) == 11 and phone.startswith("09")):
        await update.message.reply_text(
            "فرمت کپشن اشتباه است❌\n\n"
            "شماره باید 11 رقمی باشد و با 09 شروع شود.\n"
            "مثلاً: `09123456789` یا `۰۹۱۲۳۴۵۶۷۸۹`\n"
            "و کد باید 4 رقمی باشد."
        )
        return

    if not (photo_code.isdigit() and len(photo_code) == 4):
        await update.message.reply_text(
            "کد عکس باید 4 رقمی باشد.\n" "مثلاً: `1234` یا `۱۲۳۴`"
        )
        return

    conn = get_db_connection()
    c = conn.cursor()

    c.execute(
        """
        SELECT user_id FROM photo_requests 
        WHERE phone = ? AND photo_code = ? AND branch = ?
        ORDER BY created_at DESC LIMIT 1
    """,
        (phone, photo_code, branch),
    )
    result = c.fetchone()

    if result:
        user_id = result[0]
        try:
            if update.message.photo:
                file_id = update.message.photo[-1].file_id
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption=PHOTO_DELIVERED_MESSAGE,
                    parse_mode="Markdown",
                )
            elif update.message.document:
                file_id = update.message.document.file_id
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=PHOTO_DELIVERED_MESSAGE,
                    parse_mode="Markdown",
                )

            c.execute(
                """
                UPDATE photo_requests 
                SET status = 'sent', sent_at = CURRENT_TIMESTAMP
                WHERE phone = ? AND photo_code = ? AND branch = ? AND status = 'pending'
            """,
                (phone, photo_code, branch),
            )
            conn.commit()

            await update.message.reply_text(
                f"✅ عکس برای شماره {phone} با کد {photo_code} در شعبه {branch} ارسال شد."
            )

            keyboard = ReplyKeyboardMarkup([[BTN_YES], [BTN_NO]], resize_keyboard=True)

            context.user_data["admin_upload"] = {
                "phone": phone,
                "photo_code": photo_code,
                "branch": branch,
                "user_id": user_id,
                "count": 1,
            }

            await update.message.reply_text(
                "📸 آیا عکس دیگری برای این مشتری دارید؟\n\n"
                f"📱 شماره: {phone}\n"
                f"🏷️ کد: {photo_code}\n\n"
                "✅ اگر بله، عکس بعدی را ارسال کنید (بدون کپشن)\n"
                "❌ اگر نه، روی 'نه، تمام شد' کلیک کنید.",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

        except Exception as e:
            c.execute(
                """
                UPDATE photo_requests 
                SET status = 'failed', failed_reason = ?
                WHERE phone = ? AND photo_code = ? AND branch = ?
            """,
                (str(e), phone, photo_code, branch),
            )
            conn.commit()
            await update.message.reply_text(f"❌ ارسال ناموفق! خطا: {e}")
    else:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document:
            file_id = update.message.document.file_id
        else:
            file_id = None

        if file_id:
            saved = save_preuploaded_photo(
                phone=phone,
                photo_code=photo_code,
                branch=branch,
                file_id=file_id,
                admin_id=update.effective_user.id,
                message_id=update.message.message_id,
            )
            if saved:
                await update.message.reply_text(
                    f"✅ عکس برای شماره `{phone}` و کد `{photo_code}` ذخیره شد.\n\n"
                    "🔹 تا زمانی که مشتری در ربات درخواست خودش را ثبت کند، این عکس نگه داشته می‌شود و بعدا برای او ارسال خواهد شد.",
                    parse_mode="Markdown",
                )
                conn.close()
                return

        await update.message.reply_text(
            f"✅ عکس برای شماره `{phone}` و کد `{photo_code}` ذخیره شد.\n\n"
            "🔹 تا زمانی که مشتری در ربات درخواست خودش را ثبت کند، این عکس نگه داشته می‌شود و بعدا برای او ارسال خواهد شد.",
            parse_mode="Markdown",
        )

    conn.close()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """هندلر خطای سراسری برای ثبت و نمایش traceback کامل خطاها"""
    print(f"\n🔴❌ Exception جهانی رخ داد:")
    print(f"  update type: {type(update).__name__ if update else 'None'}")
    if context.error:
        print(f"  error: {context.error}")
        print(f"  traceback:\n{traceback.format_exc()}")


def main():
    init_db()
    init_admin_user()
    app = Application.builder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="back_to_menu"))
    app.add_handler(CallbackQueryHandler(users_log_callback, pattern="users_log"))
    app.add_handler(CallbackQueryHandler(usage_log_callback, pattern="usage_log"))
    app.add_handler(
        CallbackQueryHandler(
            claim_reward_callback,
            pattern=r"^claim_reward(?:\|.*)?$",
        )
    )

    # ثبت گیف نظرسنجی توسط ادمین (انیمیشن/ویدیو/فایل در چت خصوصی)
    # نکته: filters.Document.ANIMATION در python-telegram-bot وجود ندارد؛
    # گیف‌های معمولی با filters.ANIMATION و گیف‌هایی که به‌صورت فایل ارسال
    # شوند با filters.Document.ALL پوشش داده می‌شوند (هندلر خودش نوع فایل
    # را بررسی می‌کند و فایل غیر ویدیویی را با پیام خطا رد می‌کند).
    app.add_handler(
        MessageHandler(
            (filters.ANIMATION | filters.VIDEO | filters.Document.ALL)
            & filters.ChatType.PRIVATE,
            handle_review_gif_media,
        )
    )

    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL)
            & filters.Chat(chat_id=GROUP_MASHHAD_PHOTO),
            handle_group_photo,
        )
    )
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL)
            & filters.Chat(chat_id=GROUP_TEHRAN_PHOTO),
            handle_group_photo,
        )
    )

    # دکمه‌های «عکس دیگری دارم / تمام شد» در گروه‌های کاری عکس
    for photo_group_chat_id in (GROUP_MASHHAD_PHOTO, GROUP_TEHRAN_PHOTO):
        app.add_handler(
            MessageHandler(
                filters.TEXT
                & ~filters.COMMAND
                & filters.Chat(chat_id=photo_group_chat_id),
                handle_photo_group_text,
            )
        )

    # دکمه کیبورد «✅ نظر دادم» برای دریافت امتیاز هدیه
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^✅ نظر دادم$") & filters.ChatType.PRIVATE,
            claim_reward_button_handler,
        )
    )

    # دکمه کیبورد «✅ نظر دادم نشان» برای دریافت 50 امتیاز از نشان
    app.add_handler(
        MessageHandler(
            filters.Regex(rf"^{re.escape(NSHN_BUTTON_TEXT)}$") & filters.ChatType.PRIVATE,
            nshn_claim_button_handler,
        )
    )

    # پیام‌های متنی فقط در چت خصوصی پردازش می‌شوند تا گروه‌ها پیام اضافه (مثل
    # «شما از کانال خارج شدید») دریافت نکنند
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            handle_all_messages,
        )
    )

    app.add_error_handler(error_handler)

    print("BOT IS UP...")
    app.run_polling()


if __name__ == "__main__":
    main()
