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

TMP_DB = os.path.join(tempfile.gettempdir(), "pesarankarim_validate_survey_reward.db")
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

CUSTOMER_MASHHAD = 901001001
CUSTOMER_LOW_RATING = 901001002
CUSTOMER_TEHRAN = 901001003
CUSTOMER_GROUP = 901001004
ADMIN = bot.MAIN_ADMIN_ID

PHONE_MASHHAD = "09121112233"
PHOTO_CODE = "4321"
PHOTO_DATE = "1404/03/03"
REASON = "غذا سرد بود و برخورد پرسنل خوب نبود"

RESULTS = []


def check(name, condition, extra=""):
    RESULTS.append(bool(condition))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  ->  {extra}" if extra else ""))


class FakeMessage:
    def __init__(self, text=None, chat_id=1, animation=None, caption=None):
        self.text = text
        self.chat_id = chat_id
        self.message_id = 10
        self.animation = animation
        self.video = None
        self.document = None
        self.photo = None
        self.caption = caption
        self.reply_text = AsyncMock()


class FakeUser:
    def __init__(self, user_id, first_name="کاربر تست", username=None):
        self.id = user_id
        self.first_name = first_name
        self.last_name = None
        self.username = username


class FakeCallbackQuery:
    def __init__(self, user, data):
        self.from_user = user
        self.data = data
        self.answer = AsyncMock()
        self.edit_message_reply_markup = AsyncMock()
        self.edit_message_text = AsyncMock()


def make_update(user, text=None, chat_id=1, message=None):
    return types.SimpleNamespace(
        effective_user=user,
        effective_chat=types.SimpleNamespace(type="private"),
        message=message or FakeMessage(text, chat_id=chat_id),
        callback_query=None,
    )


def make_callback_update(user, data):
    return types.SimpleNamespace(
        effective_user=user,
        effective_chat=types.SimpleNamespace(type="private"),
        message=None,
        callback_query=FakeCallbackQuery(user, data),
    )


def make_context(user_data=None):
    """ساخت context تست همراه با ثبت ترتیب فراخوانی‌های ربات"""
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
    bot_stub.send_photo = recorder("send_photo")
    bot_stub.send_document = recorder("send_document")
    bot_stub.send_animation = recorder("send_animation")
    bot_stub.send_video = recorder("send_video")
    bot_stub.copy_message = recorder("copy_message")
    bot_stub.delete_message = recorder("delete_message")
    bot_stub.get_chat_member = recorder("get_chat_member")

    return types.SimpleNamespace(
        user_data=user_data if user_data is not None else {}, bot=bot_stub
    )


def messages_to(context, chat_id):
    """متن پیام‌هایی که ربات برای یک چت فرستاده است"""
    return [
        kwargs.get("text")
        for name, kwargs in context.bot.call_log
        if name == "send_message" and kwargs.get("chat_id") == chat_id
    ]


def reply_texts(update):
    """متن پاسخ‌های مستقیم ربات به پیام کاربر (reply_text)"""
    return [call.args[0] for call in update.message.reply_text.await_args_list]


def reply_markup_from_reply(update, text):
    """دکمه‌های پاسخ مستقیمی که متن مشخصی دارد"""
    for call in update.message.reply_text.await_args_list:
        if call.args and call.args[0] == text:
            return call.kwargs.get("reply_markup")
    return None


def events_to(context, chat_id):
    """رویدادهای ارسالی برای یک چت به ترتیب"""
    events = []
    for name, kwargs in context.bot.call_log:
        if kwargs.get("chat_id") != chat_id:
            continue
        if name == "send_message":
            events.append(("message", kwargs.get("text")))
        elif name == "copy_message":
            events.append(("copy", kwargs.get("message_id")))
        elif name == "send_animation":
            events.append(("animation", kwargs.get("animation")))
        elif name == "send_photo":
            events.append(("photo", kwargs.get("photo")))
        elif name == "send_document":
            events.append(("document", kwargs.get("document")))
        elif name == "send_video":
            events.append(("video", kwargs.get("video")))
    return events


def reply_markup_of(context, chat_id, text):
    """دکمه‌های پیامی مشخص که برای یک چت ارسال شده است"""
    for name, kwargs in context.bot.call_log:
        if (
            name == "send_message"
            and kwargs.get("chat_id") == chat_id
            and kwargs.get("text") == text
        ):
            return kwargs.get("reply_markup")
    return None


def keyboard_texts(markup):
    if markup is None or not hasattr(markup, "keyboard"):
        return []
    return [button.text for row in markup.keyboard for button in row]


def inline_buttons(markup):
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return []
    return [button for row in markup.inline_keyboard for button in row]


def db_rows(query, params=()):
    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def survey_row(user_id):
    rows = db_rows(
        "SELECT * FROM surveys WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    )
    return rows[0] if rows else None


def survey_count(user_id):
    return len(db_rows("SELECT id FROM surveys WHERE user_id = ?", (user_id,)))


db_module.init_db()
db_module.init_admin_user()

# ---------------------------------------------------------------------------
# ۱) متن‌ها و دکمه‌های جریان نظرسنجی
# ---------------------------------------------------------------------------
print("\n=== ۱) متن‌ها و دکمه‌های نظرسنجی ===")

check(
    "پرسش اول شامل «از ۵ ستاره به ما ۵ ستاره می‌دهید؟» است",
    "از ۵ ستاره به ما ۵ ستاره می‌دهید؟" in bot.SURVEY_FIVE_STAR_QUESTION,
)
check(
    "دکمه پاسخ بله برای ۵ ستاره درست است",
    bot.BTN_SURVEY_YES.text == "بله، ۵ ستاره میدم",
    bot.BTN_SURVEY_YES.text,
)
check("دکمه پاسخ خیر درست است", bot.BTN_SURVEY_NO.text == "خیر", bot.BTN_SURVEY_NO.text)
check(
    "پاسخ‌های بله/خیر در مجموعه متن‌های مجاز هستند",
    bot.BTN_SURVEY_YES.text in bot.SURVEY_YES_TEXTS
    and bot.BTN_SURVEY_NO.text in bot.SURVEY_NO_TEXTS,
)
check(
    "پیام تحویل عکس همان متن خواسته‌شده است",
    bot.PHOTO_DELIVERED_MESSAGE.startswith(
        "فایل اصلی عکستون با کیفیت بالا تقدیم محضر باسعادتتون"
    )
    and "www.pesaranekarim.rest" in bot.PHOTO_DELIVERED_MESSAGE
    and "Instagram.com/pesaranekarim" in bot.PHOTO_DELIVERED_MESSAGE,
)
check(
    "پیام سپاسگزاری رضایت شامل امضای خواسته‌شده است",
    bot.REWARD_THANKS_MESSAGE
    == "از مهر ماندگار شما صمیمانه سپاسگزاریم و امیدواریم بتونیم مجددا توفیق میزبانی شمارو داشته باشیم🙏😇🌸",
)
check("امتیاز هدیه ۱۰ است", bot.REWARD_POINTS == 10, str(bot.REWARD_POINTS))
check(
    "شماره پیام گیف نظرسنجی گروه‌ها خوانده می‌شود",
    bot.review_gif_message_id("mashhad") == 3
    and bot.review_gif_message_id("tehran") == 3,
)

# ---------------------------------------------------------------------------
# ۲) تحویل عکس پیش‌آپلود: پیام تحویل عکس و شروع نظرسنجی
# ---------------------------------------------------------------------------
print("\n=== ۲) تحویل عکس و شروع نظرسنجی ===")

db_module.save_preuploaded_photo(
    phone=PHONE_MASHHAD,
    photo_code=PHOTO_CODE,
    branch="mashhad",
    file_id="PREUPLOAD_FILE_ID",
    admin_id=ADMIN,
    message_id=15,
    file_type="photo",
)

delivery_context = make_context(
    {
        "branch": "mashhad",
        "photo_branch": "mashhad",
        "photo_step": "phone",
        "photo_code": PHOTO_CODE,
        "photo_date": PHOTO_DATE,
    }
)
asyncio.run(
    bot.handle_all_messages(
        make_update(FakeUser(CUSTOMER_MASHHAD, first_name="مشتری مشهد"), PHONE_MASHHAD),
        delivery_context,
    )
)

customer_events = events_to(delivery_context, CUSTOMER_MASHHAD)
check(
    "عکس پیش‌آپلود برای مشتری ارسال شد",
    [name for name, _ in customer_events].count("photo") == 1,
    str(customer_events),
)


def sent_captions(context, chat_id):
    """کپشن فایل‌های ارسال‌شده برای یک چت"""
    return [
        kwargs.get("caption")
        for name, kwargs in context.bot.call_log
        if kwargs.get("chat_id") == chat_id
        and name in ("send_photo", "send_document", "send_animation", "send_video")
    ]


check(
    "کپشن عکس تحویل، همان متن «فایل اصلی عکستون...» است",
    bot.PHOTO_DELIVERED_MESSAGE in sent_captions(delivery_context, CUSTOMER_MASHHAD),
    str(sent_captions(delivery_context, CUSTOMER_MASHHAD)),
)
check(
    "پیام تحویل عکس دیگر به‌صورت پیام جداگانه ارسال نمی‌شود",
    ("message", bot.PHOTO_DELIVERED_MESSAGE) not in customer_events,
)
check(
    "بعد از پیام تحویل عکس، پرسش ۵ ستاره ارسال شد",
    ("message", bot.SURVEY_FIVE_STAR_QUESTION) in customer_events,
)
check(
    "ترتیب پیام‌ها درست است (تحویل عکس ← پرسش نظرسنجی)",
    customer_events.index(("message", bot.SURVEY_FIVE_STAR_QUESTION)) > 0,
)
check(
    "دکمه‌های بله/خیر همراه پرسش ارسال شد",
    keyboard_texts(
        reply_markup_of(delivery_context, CUSTOMER_MASHHAD, bot.SURVEY_FIVE_STAR_QUESTION)
    )
    == [bot.BTN_SURVEY_YES.text, bot.BTN_SURVEY_NO.text],
    str(
        keyboard_texts(
            reply_markup_of(
                delivery_context, CUSTOMER_MASHHAD, bot.SURVEY_FIVE_STAR_QUESTION
            )
        )
    ),
)
check(
    "وضعیت نظرسنجی مشتری روی مرحله ۵ ستاره است",
    delivery_context.user_data.get("survey_step") == "five_star",
)

# ---------------------------------------------------------------------------
# ۳) مسیر «بله، ۵ ستاره میدم»: گوگل مپ ← گیف ← هدیه ۱۰ امتیاز
# ---------------------------------------------------------------------------
print("\n=== ۳) مسیر اعلام رضایت ۵ ستاره ===")

delivery_context.bot.call_log.clear()
asyncio.run(
    bot.handle_all_messages(
        make_update(FakeUser(CUSTOMER_MASHHAD), bot.BTN_SURVEY_YES.text),
        delivery_context,
    )
)

review_events = events_to(delivery_context, CUSTOMER_MASHHAD)
check(
    "پیام تشکر و لینک گوگل مپ ارسال شد",
    ("message", bot.GOOGLE_REVIEW_MESSAGE) in review_events,
)
check(
    "پیام گیف گروه لیست انتظار برای مشتری کپی شد",
    ("copy", bot.review_gif_message_id("mashhad")) in review_events,
)
check(
    "بعد از گیف، منوی اصلی برای مشتری ارسال می‌شود",
    ("message", "لطفا یکی از گزینه‌های زیر را انتخاب کنید:") in review_events,
)
check(
    "ترتیب پیام‌ها: تشکر و گوگل مپ ← گیف ← منوی اصلی",
    review_events
    == [
        ("message", bot.GOOGLE_REVIEW_MESSAGE),
        ("copy", bot.review_gif_message_id("mashhad")),
        ("message", "لطفا یکی از گزینه‌های زیر را انتخاب کنید:"),
    ],
    str(review_events),
)

copy_call = [
    kwargs
    for name, kwargs in delivery_context.bot.call_log
    if name == "copy_message"
][0]
check(
    "گیف از گروه لیست انتظار شعبه مشهد کپی می‌شود",
    copy_call.get("from_chat_id") == bot.waiting_group_chat_id("mashhad")
    and copy_call.get("chat_id") == CUSTOMER_MASHHAD,
    str(copy_call.get("from_chat_id")),
)

map_buttons = inline_buttons(
    reply_markup_of(delivery_context, CUSTOMER_MASHHAD, bot.GOOGLE_REVIEW_MESSAGE)
)
check(
    "زیر پیام تشکر، دکمه لینک گوگل مپ شعبه مشهد هست",
    len(map_buttons) == 1 and map_buttons[0].url == bot.GOOGLE_MAP_MASHHAD,
    str([getattr(b, "url", None) for b in map_buttons]),
)

review_done_buttons = inline_buttons(copy_call.get("reply_markup"))
check(
    "دکمه «✅ نظر دادم» زیر گیف هست",
    len(review_done_buttons) == 1
    and review_done_buttons[0].text == "✅ نظر دادم"
    and review_done_buttons[0].callback_data == "claim_reward|mashhad",
    str([getattr(b, "callback_data", None) for b in review_done_buttons]),
)
check(
    "نظرسنجی ۵ ستاره برای مشتری ذخیره شد",
    (survey_row(CUSTOMER_MASHHAD) or {}).get("rating") == 5,
)
check(
    "وضعیت نظرسنجی بعد از اعلام رضایت پاک شد",
    delivery_context.user_data.get("survey_step") is None,
)
check(
    "درخواست عکس مشتری با شماره ثبت‌شده در دسترس است",
    bot.get_last_request_phone(CUSTOMER_MASHHAD) == PHONE_MASHHAD,
)

# ---------------------------------------------------------------------------
# ۴) دکمه «دریافت ۱۰ امتیاز»
# ---------------------------------------------------------------------------
print("\n=== ۴) دکمه دریافت ۱۰ امتیاز ===")

claim_context = make_context()
claim_update = make_callback_update(
    FakeUser(CUSTOMER_MASHHAD, first_name="مشتری مشهد"), "claim_reward|mashhad"
)
asyncio.run(bot.claim_reward_callback(claim_update, claim_context))

claim_rows = db_rows(
    "SELECT * FROM review_rewards WHERE user_id = ?", (CUSTOMER_MASHHAD,)
)
check("اعلام دریافت امتیاز در دیتابیس ثبت شد", len(claim_rows) == 1)
check(
    "شماره تلفن مشتری همراه اعلام ذخیره شد",
    claim_rows and claim_rows[0]["phone"] == PHONE_MASHHAD,
    str(claim_rows[0]["phone"] if claim_rows else None),
)
check(
    "شعبه اعلام‌شده مشهد است",
    claim_rows and claim_rows[0]["branch"] == "mashhad",
)

thanks_events = events_to(claim_context, CUSTOMER_MASHHAD)
check(
    "اول پیام تبریک و دریافت امتیاز و بعد پیام سپاسگزاری و منوی اصلی ارسال شد",
    len(thanks_events) == 3
    and "تبریک" in (thanks_events[0][1] or "")
    and f"{bot.REWARD_POINTS} امتیاز هدیه" in (thanks_events[0][1] or "")
    and thanks_events[1][1] == bot.REWARD_THANKS_MESSAGE,
    str(thanks_events),
)
check(
    "دکمه دریافت امتیاز بعد از استفاده حذف شد",
    claim_update.callback_query.edit_message_reply_markup.await_count == 1
    and claim_update.callback_query.edit_message_reply_markup.await_args.kwargs
    == {"reply_markup": None},
)
check(
    "به کاربر پیام تایید دکمه نمایش داده شد",
    claim_update.callback_query.answer.await_count == 1,
)

# ---------------------------------------------------------------------------
# ۵) مسیر «خیر»: امتیاز ۱ تا ۴ ستاره و ثبت دلیل نارضایتی
# ---------------------------------------------------------------------------
print("\n=== ۵) مسیر نارضایتی: امتیاز ۱ تا ۴ ستاره ===")

no_context = make_context({"branch": "mashhad"})
asyncio.run(bot.start_survey(no_context, CUSTOMER_LOW_RATING, "mashhad"))

no_update = make_update(
    FakeUser(CUSTOMER_LOW_RATING, first_name="مشتری ناراضی"), bot.BTN_SURVEY_NO.text
)
asyncio.run(bot.handle_all_messages(no_update, no_context))

check(
    "پیام درخواست امتیاز ۱ تا ۴ ستاره ارسال شد",
    bot.LOW_RATING_REQUEST_MESSAGE in reply_texts(no_update),
)
check(
    "دکمه‌های ۴ تا ۱ ستاره همراه پیام ارسال شد",
    keyboard_texts(
        reply_markup_from_reply(no_update, bot.LOW_RATING_REQUEST_MESSAGE)
    )
    == [
        bot.BTN_STAR_4.text,
        bot.BTN_STAR_3.text,
        bot.BTN_STAR_2.text,
        bot.BTN_STAR_1.text,
        bot.BTN_BACK_TEXT,
    ],
    str(keyboard_texts(reply_markup_from_reply(no_update, bot.LOW_RATING_REQUEST_MESSAGE))),
)
check(
    "وضعیت نظرسنجی روی مرحله امتیاز زیر ۵ ستاره است",
    no_context.user_data.get("survey_step") == "rating_low",
)

no_context.bot.call_log.clear()
star_update = make_update(FakeUser(CUSTOMER_LOW_RATING), bot.BTN_STAR_2.text)
asyncio.run(bot.handle_all_messages(star_update, no_context))

low_survey = survey_row(CUSTOMER_LOW_RATING)
check("امتیاز انتخابی (۲ ستاره) ذخیره شد", (low_survey or {}).get("rating") == 2)
check(
    "بعد از انتخاب امتیاز، دلیل نارضایتی پرسیده شد",
    any("دلیل نارضایتی" in text for text in reply_texts(star_update)),
    str(reply_texts(star_update)),
)
check(
    "دکمه بازگشت همراه درخواست دلیل ارسال شد",
    keyboard_texts(
        reply_markup_from_reply(star_update, reply_texts(star_update)[0])
    )
    == [bot.BTN_BACK_TEXT],
)
check(
    "وضعیت نظرسنجی روی مرحله ثبت دلیل است",
    no_context.user_data.get("survey_step") == "low_rating_reason",
)
check(
    "شناسه نظرسنجی برای ثبت دلیل نگه داشته شد",
    no_context.user_data.get("survey_id") == (low_survey or {}).get("id"),
)

no_context.bot.call_log.clear()
reason_update = make_update(FakeUser(CUSTOMER_LOW_RATING), REASON)
asyncio.run(bot.handle_all_messages(reason_update, no_context))

low_survey = survey_row(CUSTOMER_LOW_RATING)
check("دلیل نارضایتی روی همان نظرسنجی ثبت شد", low_survey.get("comment") == REASON)
check("برای این مشتری فقط یک نظرسنجی ثبت شد", survey_count(CUSTOMER_LOW_RATING) == 1)

complaint_texts = [
    kwargs.get("text")
    for name, kwargs in no_context.bot.call_log
    if name == "send_message"
    and kwargs.get("chat_id") == bot.GROUP_MASHHAD_COMPLAINT
]
check("پیام نارضایتی به گروه نارضایتی مشهد ارسال شد", len(complaint_texts) == 1)
check(
    "پیام نارضایتی شامل امتیاز و دلیل نارضایتی است",
    complaint_texts
    and "⭐ امتیاز: 2" in complaint_texts[0]
    and REASON in complaint_texts[0],
    complaint_texts[0] if complaint_texts else "",
)
check(
    "پیام تشکر از ثبت نظر برای مشتری ارسال شد",
    any("با تشکر از شما" in text for text in reply_texts(reason_update)),
)
check(
    "وضعیت نظرسنجی بعد از ثبت دلیل پاک شد",
    no_context.user_data.get("survey_step") is None,
)

# ---------------------------------------------------------------------------
# ۶) گیف ثبت‌شده در پنل مدیریت (شعبه تهران)
# ---------------------------------------------------------------------------
print("\n=== ۶) گیف ثبت‌شده در پنل مدیریت ===")

check(
    "ثبت گیف نظرسنجی شعبه تهران در دیتابیس",
    db_module.save_review_gif("tehran", "TEHRAN_GIF_FILE_ID", "animation", "کپشن گیف تهران"),
)
check(
    "گیف ثبت‌شده خوانده می‌شود",
    (db_module.get_review_gif("tehran") or {}).get("file_id") == "TEHRAN_GIF_FILE_ID",
)

tehran_context = make_context({"branch": "tehran"})
asyncio.run(bot.start_survey(tehran_context, CUSTOMER_TEHRAN, "tehran"))
tehran_context.bot.call_log.clear()
asyncio.run(
    bot.handle_all_messages(
        make_update(FakeUser(CUSTOMER_TEHRAN, first_name="مشتری تهران"), bot.BTN_SURVEY_YES.text),
        tehran_context,
    )
)

tehran_events = events_to(tehran_context, CUSTOMER_TEHRAN)
check(
    "به‌جای کپی پیام گروه، گیف ثبت‌شده ارسال شد",
    ("animation", "TEHRAN_GIF_FILE_ID") in tehran_events
    and not any(name == "copy" for name, _ in tehran_events),
    str(tehran_events),
)

animation_call = [
    kwargs
    for name, kwargs in tehran_context.bot.call_log
    if name == "send_animation"
][0]
check(
    "کپشن ثبت‌شده همراه گیف ارسال شد",
    animation_call.get("caption") == "کپشن گیف تهران",
)
tehran_review_buttons = inline_buttons(animation_call.get("reply_markup"))
check(
    "دکمه «✅ نظر دادم» زیر گیف ثبت‌شده تهران هست",
    len(tehran_review_buttons) == 1
    and tehran_review_buttons[0].text == "✅ نظر دادم"
    and tehran_review_buttons[0].callback_data == "claim_reward|tehran",
    str([getattr(b, "callback_data", None) for b in tehran_review_buttons]),
)
check(
    "زیر پیام تشکر تهران، دکمه لینک گوگل مپ تهران هست",
    [
        button.url
        for button in inline_buttons(
            reply_markup_of(tehran_context, CUSTOMER_TEHRAN, bot.GOOGLE_REVIEW_MESSAGE)
        )
    ]
    == [bot.GOOGLE_MAP_TEHRAN],
)

# ---------------------------------------------------------------------------
# ۷) پنل مدیریت: دریافت‌های ۱۰ امتیاز و ثبت گیف
# ---------------------------------------------------------------------------
print("\n=== ۷) پنل مدیریت ===")

panel_buttons = keyboard_texts(bot.admin_panel_kb())
check(
    "دکمه «دریافت‌های ۱۰ امتیاز» در پنل مدیریت هست",
    bot.BTN_ADMIN_REWARD_CLAIMS.text in panel_buttons,
)
check(
    "دکمه «گیف نظرسنجی» در پنل مدیریت هست",
    bot.BTN_ADMIN_REVIEW_GIF.text in panel_buttons,
)

admin_user = FakeUser(ADMIN, first_name="مدیر")
claims_update = make_update(admin_user, bot.BTN_ADMIN_REWARD_CLAIMS.text)
claims_context = make_context()
asyncio.run(bot.admin_reward_claims(claims_update, claims_context))
claims_text = claims_update.message.reply_text.await_args[0][0]
check(
    "لیست دریافت‌های ۱۰ امتیاز برای مدیر نمایش داده شد",
    f"اعلام‌های دریافت {bot.REWARD_POINTS} امتیاز" in claims_text,
)
check(
    "شماره تلفن مشتری در لیست مدیر آمده است",
    PHONE_MASHHAD in claims_text,
    claims_text.replace("\n", " | "),
)
check(
    "آمار دریافت‌ها (کل/امروز) در لیست مدیر آمده است",
    "📊 کل اعلام‌ها: 1" in claims_text and "🆕 اعلام امروز: 1" in claims_text,
)
check(
    "ادامه بررسی واقعی نظر ۵ ستاره به مدیر یادآوری شده است",
    "ثبت واقعی نظرشان بررسی شود" in claims_text,
)

gif_update = make_update(admin_user, bot.BTN_ADMIN_REVIEW_GIF.text)
gif_context = make_context()
asyncio.run(bot.admin_review_gif(gif_update, gif_context))
gif_panel_text = gif_update.message.reply_text.await_args[0][0]
check(
    "وضعیت گیف هر دو شعبه برای مدیر نمایش داده شد",
    "گیف ثبت‌شده در پنل مدیریت" in gif_panel_text
    and "پیام گروه لیست انتظار" in gif_panel_text,
    gif_panel_text.replace("\n", " | "),
)
check(
    "دکمه‌های ثبت/حذف گیف هر شعبه ساخته شد",
    keyboard_texts(bot.review_gif_kb())
    == [
        bot.BTN_GIF_MASHHAD.text,
        bot.BTN_GIF_TEHRAN.text,
        bot.BTN_GIF_DELETE_MASHHAD.text,
        bot.BTN_GIF_DELETE_TEHRAN.text,
        bot.BTN_ADMIN_BACK.text,
    ],
)

register_update = make_update(
    admin_user, bot.BTN_GIF_MASHHAD.text, message=FakeMessage(bot.BTN_GIF_MASHHAD.text)
)
register_context = make_context()
asyncio.run(
    bot.handle_all_messages(register_update, register_context)
)
check(
    "با انتخاب شعبه، حالت ثبت گیف فعال می‌شود",
    register_context.user_data.get("admin_action") == "review_gif"
    and register_context.user_data.get("review_gif_branch") == "mashhad",
)

media_update = make_update(
    admin_user,
    message=FakeMessage(
        chat_id=ADMIN,
        animation=types.SimpleNamespace(file_id="MASHHAD_GIF_FILE_ID"),
        caption="کپشن گیف مشهد",
    ),
)
media_context = make_context(
    {"admin_action": "review_gif", "review_gif_branch": "mashhad"}
)
asyncio.run(bot.handle_review_gif_media(media_update, media_context))
check(
    "گیف ارسالی ادمین برای شعبه مشهد ثبت شد",
    (db_module.get_review_gif("mashhad") or {}).get("file_id") == "MASHHAD_GIF_FILE_ID",
)
check(
    "حالت ثبت گیف بعد از ثبت پاک شد",
    media_context.user_data.get("admin_action") is None
    and media_context.user_data.get("review_gif_branch") is None,
)
check(
    "پیام تایید ثبت گیف برای ادمین ارسال شد",
    "گیف نظرسنجی" in media_update.message.reply_text.await_args[0][0],
)

delete_context = make_context()
asyncio.run(
    bot.handle_all_messages(
        make_update(
            admin_user,
            bot.BTN_GIF_DELETE_TEHRAN.text,
            message=FakeMessage(bot.BTN_GIF_DELETE_TEHRAN.text),
        ),
        delete_context,
    )
)
check(
    "با دکمه حذف، گیف ثبت‌شده تهران پاک شد",
    db_module.get_review_gif("tehran") is None,
)

# ---------------------------------------------------------------------------
# ۸) گروه‌های کاری عکس: دکمه «نه، تمام شد»
# ---------------------------------------------------------------------------
print("\n=== ۸) گروه کاری عکس ===")

group_context = make_context(
    {
        "admin_upload": {
            "phone": "09123334455",
            "photo_code": "7788",
            "branch": "mashhad",
            "user_id": CUSTOMER_GROUP,
            "count": 2,
            "step": "asking",
        }
    }
)
group_update = make_update(
    FakeUser(ADMIN, first_name="مدیر"),
    bot.BTN_NO.text,
    chat_id=bot.GROUP_MASHHAD_PHOTO,
    message=FakeMessage(bot.BTN_NO.text, chat_id=bot.GROUP_MASHHAD_PHOTO),
)
asyncio.run(bot.handle_photo_group_text(group_update, group_context))

check(
    "پیام تحویل عکس دیگر برای مشتری ارسال نمی‌شود (کپشن روی خود عکس است)",
    bot.PHOTO_DELIVERED_MESSAGE not in messages_to(group_context, CUSTOMER_GROUP),
)
check(
    "کپشن عکس‌های ارسالی همان متن تحویل عکس است",
    not sent_captions(group_context, CUSTOMER_GROUP)
    or all(
        c == bot.PHOTO_DELIVERED_MESSAGE for c in sent_captions(group_context, CUSTOMER_GROUP)
    ),
)
check(
    "نظرسنجی مشتری در گروه کاری هم شروع شد",
    bot.SURVEY_FIVE_STAR_QUESTION in messages_to(group_context, CUSTOMER_GROUP),
)
check(
    "وضعیت آپلود ادمین در گروه بسته شد",
    group_context.user_data.get("admin_upload") is None,
)
check(
    "پنل مدیریت داخل گروه ارسال نشد",
    not any(
        keyboard_texts(kwargs.get("reply_markup"))
        and bot.BTN_ADMIN_MANAGE.text in keyboard_texts(kwargs.get("reply_markup"))
        for name, kwargs in group_context.bot.call_log
        if name == "send_message"
    ),
)

other_update = make_update(
    FakeUser(ADMIN),
    "سلام",
    chat_id=bot.GROUP_MASHHAD_PHOTO,
    message=FakeMessage("سلام", chat_id=bot.GROUP_MASHHAD_PHOTO),
)
other_context = make_context(
    {"admin_upload": {"phone": "1", "photo_code": "2", "branch": "mashhad", "user_id": 5}}
)
asyncio.run(bot.handle_photo_group_text(other_update, other_context))
check(
    "پیام‌های دیگر در گروه کاری بی‌پاسخ می‌مانند",
    other_update.message.reply_text.await_count == 0
    and other_context.bot.send_message.await_count == 0,
)

# ---------------------------------------------------------------------------
# نتیجه نهایی
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(
    f"تعداد تست‌ها: {len(RESULTS)} | موفق: {sum(RESULTS)} | ناموفق: {len(RESULTS) - sum(RESULTS)}"
)
print("=" * 50)

