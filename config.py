import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")

CHANNEL_USERNAME = "@pesaranekarim"
CHANNEL_ID = "-1001586571412"

GROUP_MASHHAD_PHOTO = -1004308048962
GROUP_TEHRAN_PHOTO = -1004324542601
GROUP_MASHHAD_COMPLAINT = -1004383312415
GROUP_TEHRAN_COMPLAINT = -1004419896463

MAIN_ADMIN_ID = 383415679

# ===== سازنده/مالک ربات =====
# آیدی عددی کارفرما (صاحب ربات). این آیدی‌ها همیشه به تمام بخش‌های ربات
# (پنل مدیریت، آمار، مدیریت ادمین‌ها، عکس‌های پیش‌آپلود و ...) دسترسی کامل دارند
# و از لیست ادمین‌ها قابل حذف شدن نیستند.
OWNER_ID = 193597780
SUPER_ADMIN_IDS = (OWNER_ID, MAIN_ADMIN_ID)

# اگر True باشد، همه اعضای گروه‌های عکس (مشهد و تهران) می‌توانند عکس ارسال کنند.
# اگر False شود، فقط ادمین‌ها اجازه ارسال عکس در گروه‌ها را دارند.
ALLOW_GROUP_PHOTOS_FOR_ALL = True

COOLDOWN_HOURS = 24
DB_PATH = "pesarankarim.db"

GOOGLE_MAP_MASHHAD = "https://goo.gl/maps/2uReg6JVGWT3kmXaA"
GOOGLE_MAP_TEHRAN = "https://goo.gl/1NYXYZM5rj7QLZeUA"
