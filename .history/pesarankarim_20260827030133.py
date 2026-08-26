from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
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
)
import jdatetime
import re
from config import *


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
    if clean.startswith("0") and len(clean) > 11:
        clean = clean[:11]
    return clean


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
        phone_match = re.search(r"(?:\+?98|0)[\d۰۱۲۳۴۵۶۷۸۹]{9,11}", persian_to_english_numbers(text))
        if phone_match:
            phone = normalize_phone_number(phone_match.group(0))
        code_match = re.search(r"\b\d{4}\b|\b[۰۱۲۳۴۵۶۷۸۹]{4}\b", text)
        if code_match:
            code = normalize_photo_code(code_match.group(0))

    return phone, code


async def real_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        print(f"🔍 وضعیت کاربر: {member.status}")
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"❌ خطا در بررسی عضویت: {e}")
        return False


BTN_ADD_ADMIN = KeyboardButton("➕ افزودن ادمین")
BTN_REMOVE_ADMIN = KeyboardButton("➖ حذف ادمین")
BTN_LIST_ADMINS = KeyboardButton("📋 لیست ادمین‌ها")
BTN_ADMIN_PREUPLOAD = KeyboardButton("📤 آپلود زودهنگام عکس")
BTN_ADMIN_PREUPLOAD_LIST = KeyboardButton("📋 لیست عکس‌های ذخیره‌شده")

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
BTN_ADMIN_BACK = KeyboardButton("🔙 بازگشت به منو")

BTN_YES = KeyboardButton("بله، عکس دیگری دارم")
BTN_NO = KeyboardButton("نه، تمام شد")

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


def admin_panel_kb():
    keyboard = [
        [BTN_ADMIN_STATS],
        [BTN_ADMIN_MASHHAD_PENDING, BTN_ADMIN_TEHRAN_PENDING],
        [BTN_ADMIN_MASHHAD_FAILED, BTN_ADMIN_TEHRAN_FAILED],
        [BTN_ADMIN_RESEND],
        [BTN_ADMIN_PREUPLOAD],
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
        [BTN_ADMIN_PANEL],
        [BTN_MASHHAD_PHOTO],
        [BTN_MASHHAD_APP],
        [BTN_MASHHAD_MENU, BTN_MASHHAD_FULL_MENU],
        [BTN_MASHHAD_ORDER, BTN_MASHHAD_PHONE_ORDER],
        [BTN_MASHHAD_LOCATION, BTN_MASHHAD_ADDRESS],
        [BTN_MASHHAD_SOCIAL, BTN_MASHHAD_HISTORY],
        [BTN_CHANGE_BRANCH, BTN_SUPPORT],
    ]
    # if user_id and is_admin(user_id):
    #     keyboard.insert(0, [BTN_ADMIN_PANEL])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def tehran_menu_kb(user_id=None):
    keyboard = [
        [BTN_ADMIN_PANEL],
        [BTN_TEHRAN_PHOTO],
        [BTN_TEHRAN_APP],
        [BTN_TEHRAN_MENU, BTN_TEHRAN_FULL_MENU],
        [BTN_TEHRAN_ORDER, BTN_TEHRAN_PHONE_ORDER],
        [BTN_TEHRAN_LOCATION, BTN_TEHRAN_ADDRESS],
        [BTN_TEHRAN_SOCIAL, BTN_TEHRAN_HISTORY],
        [BTN_CHANGE_BRANCH, BTN_SUPPORT],
    ]
    # if user_id and is_admin(user_id):
    #     keyboard.insert(0, [BTN_ADMIN_PANEL])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


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
        if admin_id != update.effective_user.id:
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
        text += f"{i}. {name_display}\n   🆔 آیدی: `{admin_id}`\n   🕐 افزوده شده: {added_at}\n\n"

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
            "❌ کد عکس باید 4 رقمی باشد.\n"
            "مثلاً `1234` یا `۱۲۳۴`"
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
    await update.message.reply_text(
        f"📊 آمار امروز\n\n"
        f"درخواست‌های ثبت‌شده: {stats['total_requests']}\n"
        f"✅ عکس‌های ارسال‌شده: {stats['sent_requests']}\n"
        f"⏳ در انتظار: {stats['pending_requests']}\n"
        f"❌ ارسال ناموفق: {stats['failed_requests']}\n\n"
        f"میانگین امتیاز رضایت: {stats['avg_rating']:.1f} از 5\n"
        f"🌟 تعداد 5 ستاره: {stats['five_star']}\n"
        f"تعداد نارضایتی (زیر 5): {stats['complaints']}",
        parse_mode="Markdown",
    )


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
        reply_markup=mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb(),
    )


async def start_survey(context: ContextTypes.DEFAULT_TYPE, user_id: int, branch: str):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("بله، راضی بودم")], [KeyboardButton("نه، راضی نبودم")]],
        resize_keyboard=True,
    )
    await context.bot.send_message(
        chat_id=user_id,
        text="📊 نظرسنجی رضایت\n\nاز تجربه‌ای که در رستوران پسران کریم داشتید، راضی بودید؟",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_star_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    branch = context.user_data.get("branch", "mashhad")

    star_count = text.count("⭐")
    if star_count == 0:
        return

    rating = star_count
    save_survey(user_id, rating, None, branch)

    context.user_data["survey_step"] = None

    if rating == 5:
        if branch == "mashhad":
            google_map_link = "https://goo.gl/maps/2uReg6JVGWT3kmXaA"
            branch_name = "شعبه مشهد (خیام)"
        else:
            google_map_link = "https://goo.gl/1NYXYZM5rj7QLZeUA"
            branch_name = "شعبه تهران (هتل پارسیان آزادی)"

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📍 گوگل مپ", url=google_map_link)],
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت به منو", callback_data="back_to_menu"
                    )
                ],
            ]
        )

        await update.message.reply_text(
            f"از اینکه از خدمات ما در {branch_name} راضی بودید بسیار خوشحالیم.\n\n"
            f"🙏⭐لطفا با ثبت نظر خود در گوگل مپ به ما کمک کنید تا بهتر دیده شویم.",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        context.user_data["survey_rating"] = rating
        context.user_data["survey_step"] = "low_rating_reason"
        await update.message.reply_text(
            f"⭐ امتیاز شما: {rating} از 5\n\n"
            "متاسفیم که تجربه شما کامل نبوده.\n"
            "لطفا علت آن را برای ما توضیح دهید:",
            reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
            parse_mode="Markdown",
        )


async def survey_response_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    branch = context.user_data.get("branch", "mashhad")

    if text == "بله، راضی بودم":
        context.user_data["survey_step"] = "rating"
        keyboard = ReplyKeyboardMarkup(
            [[BTN_STAR_1, BTN_STAR_2, BTN_STAR_3, BTN_STAR_4, BTN_STAR_5], [BTN_BACK]],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            "🌟 امتیاز شما به رستوران پسران کریم\n\nلطفا از 1 تا 5 ستاره به ما امتیاز دهید:",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    elif text == "نه، راضی نبودم":
        context.user_data["survey_step"] = "complaint"
        await update.message.reply_text(
            "متاسفیم که تجربه خوبی نداشتید.\n\n"
            "لطفا مشکل خود را به طور کامل برای ما بنویسید تا بتوانیم آن را برطرف کنیم:",
            reply_markup=ReplyKeyboardMarkup([[BTN_BACK]], resize_keyboard=True),
        )
        return

    elif context.user_data.get("survey_step") in ["complaint", "low_rating_reason"]:
        if text != BTN_BACK_TEXT:
            rating = context.user_data.get("survey_rating", 0)
            save_survey(user_id, rating, text, branch)

            complaint_group = (
                GROUP_MASHHAD_COMPLAINT
                if branch == "mashhad"
                else GROUP_TEHRAN_COMPLAINT
            )

            try:
                await context.bot.send_message(
                    chat_id=complaint_group,
                    text=f"📝 نارضایتی جدید\n\n"
                    f"👤 کاربر: {update.effective_user.first_name}\n"
                    f"🆔 آیدی: {user_id}\n"
                    f"📍 شعبه: {'مشهد' if branch == 'mashhad' else 'تهران'}\n"
                    f"⭐ امتیاز: {rating if rating > 0 else 'بدون امتیاز'}\n"
                    f"📝 پیام:\n{text}",
                )
            except Exception as e:
                print(f"❌ خطا در ارسال به گروه نارضایتی: {e}")

            await update.message.reply_text(
                "🙏 با تشکر از شما\n\n"
                "پیام شما ثبت شد و برای بهبود کیفیت خدمات ما بسیار ارزشمند است.",
                reply_markup=(
                    mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb()
                ),
                parse_mode="Markdown",
            )
            context.user_data["survey_step"] = None
        else:
            await update.message.reply_text(
                "🔙 به منوی اصلی بازگشتید.",
                reply_markup=(
                    mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb()
                ),
            )
        return

    elif text == "🔙 بازگشت به منو":
        await update.message.reply_text(
            "🔙 به منوی اصلی بازگشتید.",
            reply_markup=mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb(),
        )
        return


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

        await update.message.reply_text(
            f"✅ همه عکس‌ها ارسال شدند.\n\n"
            f"📱 شماره: {phone}\n"
            f"🏷️ کد: {photo_code}\n"
            f"📸 تعداد عکس‌های ارسال‌شده: {count}",
            reply_markup=admin_panel_kb(),
            parse_mode="Markdown",
        )

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
                    caption=f"📸 عکس یادگاری شما\n\n" f"📌 کد: {photo_code}",
                    parse_mode="Markdown",
                )
            else:
                await context.bot.send_document(
                    chat_id=customer_user_id,
                    document=file_id,
                    caption=f"📸 عکس یادگاری شما\n\n" f"📌 کد: {photo_code}",
                    parse_mode="Markdown",
                )

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


async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر گرامی"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🟡 ارتباط با پشتیبانی",
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

    if text in ["بله، عکس دیگری دارم", "نه، تمام شد"] and context.user_data.get(
        "admin_upload"
    ):
        await handle_admin_response(update, context)
        return

    if text == "شعبه مشهد(خیام)":
        context.user_data["branch"] = "mashhad"
        await update.message.reply_text(
            "شعبه مشهد (خیام) انتخاب شد✅\n\n"
            "برای استفاده یکی از گزینه های زیر را انتخاب کنید👇:",
            reply_markup=mashhad_menu_kb(),
            parse_mode="Markdown",
        )
        return

    elif text == "شعبه تهران(هتل پارسیان آزادی)":
        context.user_data["branch"] = "tehran"
        await update.message.reply_text(
            "شعبه تهران (هتل پارسیان آزادی) انتخاب شد✅\n\n"
            "برای استفاده یکی از گزینه های زیر را انتخاب کنید👇",
            reply_markup=tehran_menu_kb(),
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

    if (
        text in ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
        and context.user_data.get("survey_step") == "rating"
    ):
        await handle_star_selection(update, context)
        return

    if text in ["بله، راضی بودم", "نه، راضی نبودم"] or context.user_data.get(
        "survey_step"
    ):
        await survey_response_handler(update, context)
        return

    if text == "🛠️ پنل مدیریت":
        await admin_command(update, context)
        return

    elif text == "آمار":
        await admin_stats(update, context)
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

    elif text == "📤 آپلود زودهنگام عکس":
        await admin_preupload_start(update, context)
        return

    elif text == "📋 لیست عکس‌های ذخیره‌شده":
        await admin_preupload_list(update, context)
        return

    elif context.user_data.get("admin_action") == "preupload":
        await admin_preupload_phone_code(update, context)
        return

    elif context.user_data.get("admin_action") in ["add_admin", "remove_admin"]:
        await handle_admin_management(update, context)
        return

    elif text == "🔙 بازگشت به منو":
        context.user_data["in_admin_panel"] = False
        branch = context.user_data.get("branch", "mashhad")
        await update.message.reply_text(
            "🔙 به منوی اصلی بازگشتید.",
            reply_markup=mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb(),
            parse_mode="Markdown",
        )
        return

    branch = context.user_data.get("branch", "mashhad")

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
            await update.message.reply_text(
                "🔙 به منوی اصلی بازگشتید.",
                reply_markup=(
                    mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb()
                ),
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
                                "🟡 دانلود اپلیکیشن پسران کریم",
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
                                "🟡 مشاهده منو به همراه قیمت",
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
                            "🟡 مشاهده منو به همراه تصاویر",
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
                            "🟡 سفارش آنلاین", url="www.pesaranekarim.rest"
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
                    "🟡 آدرس ما:\n\n"
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
                            "✈️ سفارش تلگرامی غذا",
                            url="https://t.me/pesaranekarimdelivery",
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
                            "🟡 تاریخچه پسران کریم",
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
                f"📍 شما در شعبه تهران (هتل پارسیان آزادی) هستید.\n\n"
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
                                "🟡 دانلود اپلیکیشن پسران کریم",
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
                                "🟡 مشاهده منو به همراه قیمت",
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
                            "🟡 مشاهده منو به همراه تصویر",
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
                            "🟡 سفارش آنلاین", url="www.pesaranekarim.rest"
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
                                "🟡 مسیریابی به رستوران پسران کریم تهران",
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
                            "✈️ سفارش تلگرامی غذا",
                            url="https://t.me/pesaranekarimdelivery",
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
                            "🟡 تاریخچه پسران کریم",
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
        phone = normalize_phone_number(text)

        if phone.isdigit() and len(phone) == 11 and phone.startswith("09"):
            context.user_data["photo_phone"] = phone
            context.user_data["photo_step"] = "complete"

            photo_branch = context.user_data.get("photo_branch", "mashhad")
            photo_code = context.user_data.get("photo_code")
            photo_date = context.user_data.get("photo_date")

            preuploaded = get_preuploaded_photo(phone, photo_code, photo_branch)

            if preuploaded:
                preupload_id, file_id, message_id, created_at = preuploaded

                try:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=file_id,
                        caption="📸 عکس یادگاری شما\n\n"
                        "از اینکه رستوران پسران کریم را انتخاب کردید سپاسگزاریم🌹",
                        parse_mode="Markdown",
                    )

                    mark_preuploaded_as_used(preupload_id)

                    save_photo_request(
                        user_id=user_id,
                        phone=phone,
                        photo_code=photo_code,
                        photo_date=photo_date,
                        branch=photo_branch,
                    )

                    await update.message.reply_text(
                        "✅ عکس شما ارسال شد!\n\n"
                        "از اینکه رستوران پسران کریم را انتخاب کردید سپاسگزاریم🌹",
                        reply_markup=(
                            mashhad_menu_kb()
                            if photo_branch == "mashhad"
                            else tehran_menu_kb()
                        ),
                        parse_mode="Markdown",
                    )

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

            await update.message.reply_text(
                "درخواست شما ثبت شد✅\n\n"
                "شما در صف انتظار هستید و به محض آماده شدن عکس، فایل آن برای شما ارسال میشود.",
                reply_markup=(
                    mashhad_menu_kb() if photo_branch == "mashhad" else tehran_menu_kb()
                ),
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
            reply_markup=(
                mashhad_menu_kb() if branch == "mashhad" else tehran_menu_kb()
            ),
        )
        return


async def handle_group_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.message.chat_id
    if chat_id not in [GROUP_MASHHAD_PHOTO, GROUP_TEHRAN_PHOTO]:
        return

    if not is_admin(update.effective_user.id):
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
        elif update.message.document:
            file_id = update.message.document.file_id
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
        )

        if result:
            await update.message.reply_text(
                f"✅ عکس با موفقیت ذخیره شد!\n\n"
                f"📱 شماره: `{phone}`\n"
                f"🏷️ کد: `{photo_code}`\n"
                f"📍 شعبه: {'مشهد' if branch == 'mashhad' else 'تهران'}\n\n"
                "🔹 این عکس زمانی که مشتری درخواست داد، به صورت خودکار ارسال خواهد شد.",
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

    caption = update.message.caption or ""
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
            "کد عکس باید 4 رقمی باشد.\n"
            "مثلاً: `1234` یا `۱۲۳۴`"
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
                    caption="📸 عکس یادگاری شما:\n\n"
                    "از اینکه رستوران پسران کریم را انتخاب کردید سپاسگزاریم🌹",
                    parse_mode="Markdown",
                )
            elif update.message.document:
                file_id = update.message.document.file_id
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption="📸 عکس یادگاری شما: \n\n"
                    "از اینکه رستوران پسران کریم را انتخاب کردید سپاسگزاریم🌹",
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
        await update.message.reply_text(
            f"❌ درخواستی با شماره {phone} و کد {photo_code} در شعبه {branch} یافت نشد!\n"
            "لطفا مطمئن شوید کاربر درخواست داده است."
        )

    conn.close()


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="back_to_menu"))

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

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)
    )

    print("BOT IS UP...")
    app.run_polling()


if __name__ == "__main__":
    main()
