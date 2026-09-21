import sqlite3
from datetime import datetime, timedelta
import os
import re

try:
    from config import SUPER_ADMIN_IDS
except Exception:  # اگر config در دسترس نبود، حداقل‌های امن استفاده می‌شود
    SUPER_ADMIN_IDS = ()

DB_PATH = os.path.join(os.path.dirname(__file__), "pesarankarim.db")


def normalize_phone_for_storage(phone):
    if phone is None:
        return ""
    text = str(phone)
    persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
    english_numbers = "0123456789"
    text = text.translate(str.maketrans(persian_numbers, english_numbers))
    digits = re.sub(r"\D", "", text)

    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    elif digits.startswith("0") and len(digits) > 11:
        digits = digits[:11]

    return digits


def normalize_code_for_storage(code):
    if code is None:
        return ""
    text = str(code)
    persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
    english_numbers = "0123456789"
    text = text.translate(str.maketrans(persian_numbers, english_numbers))
    return re.sub(r"\D", "", text)


def normalize_file_type(file_type):
    if file_type is None:
        return "photo"
    value = str(file_type).strip().lower()
    if value in {"photo", "image", "jpg", "jpeg", "png", "gif"}:
        return "photo"
    if value in {"document", "file", "pdf", "doc", "docx"}:
        return "document"
    return "photo"


def repair_preuploaded_photo_rows():
    """Fix legacy or partially-missing preupload rows so uploads can still be sent safely."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("PRAGMA table_info(preuploaded_photos)")
        columns = [col[1] for col in c.fetchall()]
        if "file_type" not in columns:
            conn.close()
            return

        c.execute(
            "UPDATE preuploaded_photos SET file_type = 'photo' WHERE file_type IS NULL OR TRIM(file_type) = ''"
        )
        c.execute(
            "UPDATE preuploaded_photos SET file_type = 'photo' WHERE LOWER(TRIM(file_type)) IN ('image', 'jpg', 'jpeg', 'png', 'gif')"
        )
        c.execute(
            "UPDATE preuploaded_photos SET file_type = 'document' WHERE LOWER(TRIM(file_type)) IN ('document', 'file', 'pdf', 'doc', 'docx')"
        )
        conn.commit()
    except Exception as e:
        print(f"❌ خطا در پاک‌سازی فایل‌های پیش‌آپلود قدیمی: {e}")
    finally:
        if "conn" in locals():
            conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    def ensure_column(table_name, column_sql):
        existing = c.execute(f"PRAGMA table_info({table_name})").fetchall()
        column_name = column_sql.split()[0]
        if not any(col[1] == column_name for col in existing):
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    # ===== ۱. جدول درخواست‌های عکس با فیلد branch =====
    c.execute("""CREATE TABLE IF NOT EXISTS photo_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        photo_code TEXT NOT NULL,
        photo_date TEXT NOT NULL,
        branch TEXT NOT NULL DEFAULT 'mashhad',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sent_at TIMESTAMP,
        failed_reason TEXT,
        last_request_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ===== ۲. جدول نظرسنجی با فیلد branch =====
    c.execute("""CREATE TABLE IF NOT EXISTS surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        photo_request_id INTEGER,
        rating INTEGER,
        comment TEXT,
        branch TEXT DEFAULT 'mashhad',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (photo_request_id) REFERENCES photo_requests(id)
    )""")

    # ===== ۳. جدول ادمین‌ها =====
    c.execute("""CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        last_login TIMESTAMP,
        FOREIGN KEY (added_by) REFERENCES admins(user_id)
    )""")

    # ===== ۴. جدول تنظیمات =====
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ===== ۵. جدول تاریخچه ارسال =====
    c.execute("""CREATE TABLE IF NOT EXISTS send_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_request_id INTEGER,
        admin_id INTEGER,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        FOREIGN KEY (photo_request_id) REFERENCES photo_requests(id),
        FOREIGN KEY (admin_id) REFERENCES admins(user_id)
    )""")

    # ===== ۶. جدول گزارشات =====
    c.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY,
        total_requests INTEGER DEFAULT 0,
        sent_requests INTEGER DEFAULT 0,
        failed_requests INTEGER DEFAULT 0,
        pending_requests INTEGER DEFAULT 0,
        avg_rating REAL DEFAULT 0,
        five_star_count INTEGER DEFAULT 0,
        complaints_count INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ===== ۷. جدول عکس‌های پیش‌آپلود شده (ویژگی جدید) =====
    c.execute("""CREATE TABLE IF NOT EXISTS preuploaded_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        photo_code TEXT NOT NULL,
        branch TEXT NOT NULL DEFAULT 'mashhad',
        file_id TEXT NOT NULL,
        file_type TEXT DEFAULT 'photo',
        admin_id INTEGER,
        message_id INTEGER,
        used BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (admin_id) REFERENCES admins(user_id)
    )""")
    ensure_column("preuploaded_photos", "file_type TEXT DEFAULT 'photo'")

    # ===== ۸. جدول بلاک‌شده‌ها =====
    c.execute("""CREATE TABLE IF NOT EXISTS blocked_users (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        blocked_by INTEGER,
        FOREIGN KEY (blocked_by) REFERENCES admins(user_id)
    )""")

    # ===== ۹. جدول کاربران ربات (تاریخ عضویت در ربات) =====
    # اولین باری که کاربر ربات را استفاده کند، به عنوان عضو ربات با تاریخ عضویت ثبت می‌شود
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usage_count INTEGER DEFAULT 0
    )""")

    # ===== ۱۰. جدول لاگ استفاده از ربات =====
    # هر بار استفاده کاربر از ربات (فشردن دکمه‌ها، ثبت درخواست، نظرسنجی و ...) در این جدول ثبت می‌شود
    c.execute("""CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        action TEXT,
        detail TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ایجاد ایندکس‌ها برای سرعت بیشتر
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_photo_requests_user_id ON photo_requests(user_id)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_photo_requests_phone ON photo_requests(phone)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_photo_requests_status ON photo_requests(status)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_photo_requests_created_at ON photo_requests(created_at)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_photo_requests_branch ON photo_requests(branch)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_surveys_user_id ON surveys(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_surveys_branch ON surveys(branch)")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_send_history_photo_request_id ON send_history(photo_request_id)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_admins_is_active ON admins(is_active)")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_preuploaded_photos_phone ON preuploaded_photos(phone)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_preuploaded_photos_code ON preuploaded_photos(photo_code)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_preuploaded_photos_branch ON preuploaded_photos(branch)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_preuploaded_photos_used ON preuploaded_photos(used)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_joined_at ON users(joined_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON usage_logs(user_id)")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at)"
    )

    # ===== پر کردن جدول کاربران از داده‌های قبلی ربات =====
    # فقط زمانی اجرا می‌شود که جدول کاربران خالی باشد (یعنی یک‌بار بعد از این بروزرسانی).
    # تاریخ عضویت این کاربران دقیق نیست و با اولین فعالیت ثبت‌شده‌شان تقریب زده می‌شود.
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        for source_table in ("photo_requests", "surveys"):
            c.execute(f"""
                INSERT OR IGNORE INTO users (user_id, joined_at, last_seen)
                SELECT user_id, MIN(created_at), MAX(created_at)
                FROM {source_table}
                WHERE created_at IS NOT NULL
                GROUP BY user_id
            """)

    # ===== اطمینان از دسترسی کامل سازنده/مالک ربات =====
    # این آیدی‌ها همیشه در لیست ادمین‌ها فعال نگه داشته می‌شوند
    for super_admin_id in SUPER_ADMIN_IDS:
        c.execute(
            """
            INSERT OR IGNORE INTO admins (user_id, added_by, is_active)
            VALUES (?, ?, 1)
        """,
            (super_admin_id, super_admin_id),
        )
        c.execute(
            "UPDATE admins SET is_active = 1 WHERE user_id = ?",
            (super_admin_id,),
        )

    conn.commit()
    conn.close()

    print("DATABASE SUCCESSFULY CREATED.")


def get_db_connection():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ===== توابع مدیریت ادمین =====
def add_admin(user_id, username=None, first_name=None, last_name=None, added_by=None):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT OR IGNORE INTO admins (user_id, username, first_name, last_name, added_by, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """,
            (user_id, username, first_name, last_name, added_by or user_id),
        )
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"ERROR IN ADDING ADMIN:{e}")
        return False
    finally:
        conn.close()


def remove_admin(user_id):
    # سازنده/مالک ربات قابل حذف شدن نیست
    if is_super_admin(user_id):
        return False

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE admins SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"ERROR IN REMOVING ADMIN: {e}")
        return False
    finally:
        conn.close()


def delete_admin_permanently(user_id):
    """حذف کامل ادمین از دیتابیس"""
    # سازنده/مالک ربات قابل حذف شدن نیست
    if is_super_admin(user_id):
        return False

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"ERROR IN PERMANENT DELETE: {e}")
        return False
    finally:
        conn.close()


def is_super_admin(user_id):
    """بررسی اینکه کاربر سازنده/مالک ربات است یا نه (دسترسی کامل و همیشگی)"""
    try:
        return int(user_id) in SUPER_ADMIN_IDS
    except (TypeError, ValueError):
        return False


def is_admin(user_id):
    # سازنده/مالک ربات همیشه دسترسی کامل دارد، حتی اگر از دیتابیس حذف شود
    if is_super_admin(user_id):
        return True

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT user_id FROM admins WHERE user_id = ? AND is_active = 1", (user_id,)
    )
    result = c.fetchone()
    conn.close()
    return result is not None


def get_admins():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, username, first_name, last_name, added_at 
        FROM admins 
        WHERE is_active = 1
        ORDER BY added_at ASC
    """)
    result = c.fetchall()
    conn.close()
    return result


# ===== توابع جدید مدیریت ادمین (اضافه شده) =====
def get_all_admins(include_inactive=False):
    """دریافت لیست همه ادمین‌ها با فرمت دیکشنری"""
    conn = get_db_connection()
    c = conn.cursor()

    if include_inactive:
        c.execute("""
            SELECT user_id, username, first_name, last_name, added_at, is_active
            FROM admins
            ORDER BY added_at ASC
        """)
    else:
        c.execute("""
            SELECT user_id, username, first_name, last_name, added_at
            FROM admins 
            WHERE is_active = 1
            ORDER BY added_at ASC
        """)

    results = c.fetchall()
    conn.close()
    return [dict(row) for row in results]


def get_admin_info(user_id):
    """دریافت اطلاعات یک ادمین"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT user_id, username, first_name, last_name, added_at, is_active
        FROM admins 
        WHERE user_id = ?
    """,
        (user_id,),
    )
    result = c.fetchone()
    conn.close()
    return dict(result) if result else None


def update_admin_login(user_id):
    """به‌روزرسانی زمان آخرین ورود ادمین"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "UPDATE admins SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در بروزرسانی آخرین ورود: {e}")
        return False
    finally:
        conn.close()


# ===== توابع عکس‌های پیش‌آپلود شده =====
def save_preuploaded_photo(
    phone, photo_code, branch, file_id, admin_id, message_id=None, file_type="photo"
):
    """ذخیره عکس آپلود شده توسط ادمین در گروه"""
    init_db()
    phone = normalize_phone_for_storage(phone)
    photo_code = normalize_code_for_storage(photo_code)
    branch = (branch or "mashhad").strip().lower()
    file_type = normalize_file_type(file_type)

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO preuploaded_photos (phone, photo_code, branch, file_id, file_type, admin_id, message_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (phone, photo_code, branch, file_id, file_type, admin_id, message_id),
        )
        conn.commit()
        return c.lastrowid
    except Exception as e:
        print(f"❌ خطا در ذخیره عکس پیش‌آپلود: {e}")
        return None
    finally:
        conn.close()


def get_preuploaded_photo(phone, photo_code, branch):
    """دریافت عکس پیش‌آپلود شده با شماره و کد"""
    init_db()
    phone = normalize_phone_for_storage(phone)
    photo_code = normalize_code_for_storage(photo_code)
    branch = (branch or "mashhad").strip().lower()

    repair_preuploaded_photo_rows()
    conn = get_db_connection()
    c = conn.cursor()

    variants = [phone]
    if phone.startswith("0"):
        variants.append("98" + phone[1:])
    if phone.startswith("98"):
        variants.append("0" + phone[2:])
    variants = list(dict.fromkeys(v for v in variants if v))

    placeholders = ", ".join("?" for _ in variants)
    c.execute(
        f"""
        SELECT id, file_id, file_type, message_id, created_at
        FROM preuploaded_photos 
        WHERE phone IN ({placeholders}) AND photo_code = ? AND branch = ? AND used = 0
        ORDER BY created_at DESC LIMIT 1
    """,
        (*variants, photo_code, branch),
    )
    result = c.fetchone()
    conn.close()
    return result


def mark_preuploaded_as_used(photo_id):
    """علامت‌گذاری عکس پیش‌آپلود به عنوان استفاده شده"""
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE preuploaded_photos SET used = 1 WHERE id = ?", (photo_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در بروزرسانی عکس پیش‌آپلود: {e}")
        return False
    finally:
        conn.close()


def get_all_preuploaded_photos(branch=None):
    """دریافت لیست همه عکس‌های پیش‌آپلود شده"""
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    if branch:
        c.execute(
            """
            SELECT id, phone, photo_code, created_at, used
            FROM preuploaded_photos 
            WHERE branch = ?
            ORDER BY created_at DESC
        """,
            (branch,),
        )
    else:
        c.execute("""
            SELECT id, phone, photo_code, branch, created_at, used
            FROM preuploaded_photos 
            ORDER BY created_at DESC
        """)
    result = c.fetchall()
    conn.close()
    return result


def delete_preuploaded_photo(photo_id):
    """حذف عکس پیش‌آپلود شده"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM preuploaded_photos WHERE id = ?", (photo_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در حذف عکس پیش‌آپلود: {e}")
        return False
    finally:
        conn.close()


# ===== توابع مدیریت کاربران بلاک =====
def is_user_blocked(user_id):
    """بررسی بلاک بودن کاربر"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM blocked_users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None


def block_user(user_id, reason=None, blocked_by=None):
    """بلاک کردن کاربر"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_by, blocked_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (user_id, reason, blocked_by),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در بلاک کاربر: {e}")
        return False
    finally:
        conn.close()


def unblock_user(user_id):
    """آنبلاک کردن کاربر"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"❌ خطا در آنبلاک کاربر: {e}")
        return False
    finally:
        conn.close()


# ===== توابع درخواست عکس =====
def save_photo_request(user_id, phone, photo_code, photo_date, branch):
    """ذخیره درخواست عکس جدید با شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO photo_requests (user_id, phone, photo_code, photo_date, branch, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        """,
            (user_id, phone, photo_code, photo_date, branch),
        )
        conn.commit()
        return c.lastrowid
    except Exception as e:
        print(f"❌ خطا در ذخیره درخواست: {e}")
        return None
    finally:
        conn.close()


def get_pending_request(phone, photo_code, branch):
    """دریافت درخواست در انتظار با شماره، کد و شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, user_id, phone, photo_code, photo_date, created_at
        FROM photo_requests 
        WHERE phone = ? AND photo_code = ? AND branch = ? AND status = 'pending'
        ORDER BY created_at DESC LIMIT 1
    """,
        (phone, photo_code, branch),
    )
    result = c.fetchone()
    conn.close()
    return result


def update_photo_request_status(request_id, status, failed_reason=None):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        if status == "sent":
            c.execute(
                """
                UPDATE photo_requests 
                SET status = ?, sent_at = CURRENT_TIMESTAMP, failed_reason = NULL
                WHERE id = ?
            """,
                (status, request_id),
            )
        else:
            c.execute(
                """
                UPDATE photo_requests 
                SET status = ?, failed_reason = ?
                WHERE id = ?
            """,
                (status, failed_reason, request_id),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR IN UPDATING:{e}")
        return False
    finally:
        conn.close()


def get_request_by_phone_and_code(phone, photo_code, branch=None):
    """دریافت درخواست با شماره و کد (اختیاری با شعبه)"""
    conn = get_db_connection()
    c = conn.cursor()
    if branch:
        c.execute(
            """
            SELECT id, user_id, phone, photo_code, photo_date, status, created_at
            FROM photo_requests 
            WHERE phone = ? AND photo_code = ? AND branch = ?
            ORDER BY created_at DESC LIMIT 1
        """,
            (phone, photo_code, branch),
        )
    else:
        c.execute(
            """
            SELECT id, user_id, phone, photo_code, photo_date, status, created_at
            FROM photo_requests 
            WHERE phone = ? AND photo_code = ?
            ORDER BY created_at DESC LIMIT 1
        """,
            (phone, photo_code),
        )
    result = c.fetchone()
    conn.close()
    return dict(result) if result else None


def get_all_requests_by_branch(branch):
    """دریافت همه درخواست‌های یک شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, user_id, phone, photo_code, photo_date, status, created_at, sent_at
        FROM photo_requests 
        WHERE branch = ?
        ORDER BY created_at DESC
    """,
        (branch,),
    )
    result = c.fetchall()
    conn.close()
    return [dict(row) for row in result]


def get_user_requests(user_id):
    """دریافت همه درخواست‌های یک کاربر"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, phone, photo_code, photo_date, branch, status, created_at, sent_at
        FROM photo_requests 
        WHERE user_id = ?
        ORDER BY created_at DESC
    """,
        (user_id,),
    )
    results = c.fetchall()
    conn.close()
    return [dict(row) for row in results]


# ===== توابع نظرسنجی =====
def save_survey(user_id, rating, comment, branch="mashhad", photo_request_id=None):
    """ذخیره نظرسنجی در دیتابیس با شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO surveys (user_id, photo_request_id, rating, comment, branch, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (user_id, photo_request_id, rating, comment, branch),
        )
        conn.commit()
        return c.lastrowid
    except Exception as e:
        print(f"ERROR IN SAVING THE SURVEY: {e}")
        return None
    finally:
        conn.close()


def get_surveys_by_user(user_id):
    """دریافت نظرسنجی‌های یک کاربر"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, rating, comment, branch, created_at
        FROM surveys 
        WHERE user_id = ?
        ORDER BY created_at DESC
    """,
        (user_id,),
    )
    results = c.fetchall()
    conn.close()
    return [dict(row) for row in results]


# ===== توابع تاریخچه =====
def save_send_history(photo_request_id, admin_id, status):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO send_history (photo_request_id, admin_id, status, sent_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (photo_request_id, admin_id, status),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR IN SAVING SAVING DATE: {e}")
        return False
    finally:
        conn.close()


def get_send_history(photo_request_id):
    """دریافت تاریخچه ارسال یک درخواست"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, admin_id, status, sent_at
        FROM send_history 
        WHERE photo_request_id = ?
        ORDER BY sent_at DESC
    """,
        (photo_request_id,),
    )
    results = c.fetchall()
    conn.close()
    return [dict(row) for row in results]


# ===== توابع آمار با پشتیبانی از شعبه =====
def get_daily_stats(date=None, branch=None):
    """دریافت آمار روزانه بر اساس شعبه"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    c = conn.cursor()

    if branch:
        c.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM photo_requests 
            WHERE date(created_at) = ? AND branch = ?
        """,
            (date, branch),
        )
    else:
        c.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM photo_requests 
            WHERE date(created_at) = ?
        """,
            (date,),
        )
    requests = c.fetchone()

    if branch:
        c.execute(
            """
            SELECT AVG(rating) as avg_rating,
                   SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star,
                   SUM(CASE WHEN rating BETWEEN 1 AND 4 THEN 1 ELSE 0 END) as complaints
            FROM surveys 
            WHERE date(created_at) = ? AND branch = ?
        """,
            (date, branch),
        )
    else:
        c.execute(
            """
            SELECT AVG(rating) as avg_rating,
                   SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star,
                   SUM(CASE WHEN rating BETWEEN 1 AND 4 THEN 1 ELSE 0 END) as complaints
            FROM surveys 
            WHERE date(created_at) = ?
        """,
            (date,),
        )
    survey = c.fetchone()

    conn.close()

    return {
        "total_requests": requests[0] or 0,
        "sent_requests": requests[1] or 0,
        "pending_requests": requests[2] or 0,
        "failed_requests": requests[3] or 0,
        "avg_rating": survey[0] or 0,
        "five_star": survey[1] or 0,
        "complaints": survey[2] or 0,
    }


def get_weekly_stats(branch=None):
    """دریافت آمار هفتگی"""
    conn = get_db_connection()
    c = conn.cursor()

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    if branch:
        c.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(rating) as avg_rating
            FROM photo_requests 
            LEFT JOIN surveys ON photo_requests.id = surveys.photo_request_id
            WHERE date(photo_requests.created_at) >= ? AND photo_requests.branch = ?
        """,
            (week_ago, branch),
        )
    else:
        c.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(rating) as avg_rating
            FROM photo_requests 
            LEFT JOIN surveys ON photo_requests.id = surveys.photo_request_id
            WHERE date(photo_requests.created_at) >= ?
        """,
            (week_ago,),
        )

    result = c.fetchone()
    conn.close()

    return {
        "total_requests": result[0] or 0,
        "sent_requests": result[1] or 0,
        "pending_requests": result[2] or 0,
        "failed_requests": result[3] or 0,
        "avg_rating": round(result[4] or 0, 1),
    }


def get_pending_requests(branch=None):
    """دریافت لیست درخواست‌های در انتظار بر اساس شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    if branch:
        c.execute(
            """
            SELECT id, phone, photo_code, photo_date, created_at,
                   (strftime('%s', 'now') - strftime('%s', created_at)) / 3600 as hours
            FROM photo_requests 
            WHERE status = 'pending' AND branch = ?
            ORDER BY created_at ASC
        """,
            (branch,),
        )
    else:
        c.execute("""
            SELECT id, phone, photo_code, photo_date, created_at,
                   (strftime('%s', 'now') - strftime('%s', created_at)) / 3600 as hours
            FROM photo_requests 
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
    result = c.fetchall()
    conn.close()
    return result


def get_failed_requests(branch=None):
    """دریافت لیست ارسال‌های ناموفق بر اساس شعبه"""
    conn = get_db_connection()
    c = conn.cursor()
    if branch:
        c.execute(
            """
            SELECT id, phone, photo_code, photo_date, created_at, failed_reason
            FROM photo_requests 
            WHERE status = 'failed' AND branch = ?
            ORDER BY created_at DESC
        """,
            (branch,),
        )
    else:
        c.execute("""
            SELECT id, phone, photo_code, photo_date, created_at, failed_reason
            FROM photo_requests 
            WHERE status = 'failed'
            ORDER BY created_at DESC
        """)
    result = c.fetchall()
    conn.close()
    return result


def get_preuploaded_photo_count(branch=None):
    """دریافت تعداد عکس‌های پیش‌آپلود استفاده نشده"""
    conn = get_db_connection()
    c = conn.cursor()
    if branch:
        c.execute(
            "SELECT COUNT(*) FROM preuploaded_photos WHERE branch = ? AND used = 0",
            (branch,),
        )
    else:
        c.execute("SELECT COUNT(*) FROM preuploaded_photos WHERE used = 0")
    result = c.fetchone()[0]
    conn.close()
    return result


# ===== توابع لاگ کاربران ربات =====
# زمان‌ها در دیتابیس به وقت UTC ذخیره می‌شوند؛ برای مقایسه تاریخ «امروز» به وقت ایران
# (UTC+3:30) از این مودیفایرها استفاده می‌شود.
IRAN_TZ_SQL = "'+3 hours', '+30 minutes'"


def _iran_today_condition(column_name):
    """شرط SQL برای بررسی اینکه یک ستون زمانی مربوط به امروز (به وقت ایران) است یا نه"""
    return f"date({column_name}, {IRAN_TZ_SQL}) = date('now', {IRAN_TZ_SQL})"


def _clean_user_field(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _upsert_user(cursor, user_id, username, first_name, last_name):
    """ثبت کاربر جدید (همراه تاریخ عضویت) یا بروزرسانی اطلاعات کاربر موجود"""
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, joined_at, last_seen, usage_count)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
    """,
        (user_id, username, first_name, last_name),
    )
    cursor.execute(
        """
        UPDATE users
        SET username = COALESCE(?, username),
            first_name = COALESCE(?, first_name),
            last_name = COALESCE(?, last_name),
            last_seen = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """,
        (username, first_name, last_name, user_id),
    )


def register_user(user_id, username=None, first_name=None, last_name=None):
    """ثبت کاربر در جدول کاربران ربات

    اولین باری که کاربر با ربات کار کند، تاریخ عضویت او ثبت می‌شود و در
    استفاده‌های بعدی فقط اطلاعات و آخرین فعالیتش به‌روز می‌شود.
    """
    if user_id is None:
        return None

    username = _clean_user_field(username)
    first_name = _clean_user_field(first_name)
    last_name = _clean_user_field(last_name)

    conn = get_db_connection()
    c = conn.cursor()
    try:
        _upsert_user(c, user_id, username, first_name, last_name)
        conn.commit()
        c.execute(
            """
            SELECT user_id, username, first_name, last_name, joined_at, last_seen, usage_count
            FROM users WHERE user_id = ?
        """,
            (user_id,),
        )
        row = c.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"❌ خطا در ثبت کاربر ربات: {e}")
        return None
    finally:
        conn.close()


def log_bot_usage(
    user_id, action, detail=None, username=None, first_name=None, last_name=None
):
    """ثبت یک استفاده از ربات همراه با تاریخ عضویت کاربر

    اگر کاربر برای اولین بار باشد، ابتدا در جدول کاربران ثبت می‌شود و بعد
    لاگ استفاده از ربات برایش درج می‌گردد.
    """
    if user_id is None:
        return False

    username = _clean_user_field(username)
    first_name = _clean_user_field(first_name)
    last_name = _clean_user_field(last_name)

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # ثبت کاربر در اولین استفاده (تاریخ عضویت) و بروزرسانی اطلاعاتش
        _upsert_user(c, user_id, username, first_name, last_name)
        c.execute(
            """
            UPDATE users
            SET usage_count = COALESCE(usage_count, 0) + 1,
                last_seen = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """,
            (user_id,),
        )
        c.execute(
            """
            INSERT INTO usage_logs (user_id, username, first_name, action, detail, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                user_id,
                username,
                first_name,
                _clean_user_field(action) or "نامشخص",
                _clean_user_field(detail),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در ثبت لاگ استفاده از ربات: {e}")
        return False
    finally:
        conn.close()


def get_users_count():
    """تعداد کل کاربرانی که ربات را استفاده کرده‌اند"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    conn.close()
    return total


def get_users_log(limit=10, offset=0):
    """لیست کاربران ربات همراه با تاریخ عضویت، آخرین فعالیت و تعداد استفاده"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT u.user_id, u.username, u.first_name, u.last_name, u.joined_at, u.last_seen,
               COALESCE(u.usage_count, 0) AS usage_count,
               (SELECT COUNT(*) FROM photo_requests pr WHERE pr.user_id = u.user_id) AS requests_count,
               (SELECT COUNT(*) FROM surveys s WHERE s.user_id = u.user_id) AS surveys_count
        FROM users u
        ORDER BY u.joined_at DESC, u.user_id DESC
        LIMIT ? OFFSET ?
    """,
        (limit, offset),
    )
    result = c.fetchall()
    conn.close()
    return [dict(row) for row in result]


def get_usage_logs_count(user_id=None):
    """تعداد کل رکوردهای لاگ استفاده از ربات"""
    conn = get_db_connection()
    c = conn.cursor()
    if user_id is None:
        c.execute("SELECT COUNT(*) FROM usage_logs")
    else:
        c.execute("SELECT COUNT(*) FROM usage_logs WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    conn.close()
    return total


def get_usage_logs(limit=10, offset=0, user_id=None):
    """آخرین استفاده‌های انجام‌شده از ربات همراه با تاریخ عضویت کاربر"""
    conn = get_db_connection()
    c = conn.cursor()
    base_query = """
        SELECT l.id, l.user_id,
               COALESCE(l.username, u.username) AS username,
               COALESCE(l.first_name, u.first_name) AS first_name,
               l.action, l.detail, l.created_at,
               u.joined_at, COALESCE(u.usage_count, 0) AS usage_count
        FROM usage_logs l
        LEFT JOIN users u ON u.user_id = l.user_id
    """
    if user_id is None:
        c.execute(
            base_query + " ORDER BY l.id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    else:
        c.execute(
            base_query + " WHERE l.user_id = ? ORDER BY l.id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
    result = c.fetchall()
    conn.close()
    return [dict(row) for row in result]


def get_users_stats():
    """آمار کاربران ربات و لاگ استفاده از آن (روز جاری به وقت ایران)"""
    conn = get_db_connection()
    c = conn.cursor()
    stats = {}

    c.execute("SELECT COUNT(*) FROM users")
    stats["total_users"] = c.fetchone()[0]

    c.execute(f"SELECT COUNT(*) FROM users WHERE {_iran_today_condition('joined_at')}")
    stats["new_users_today"] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM usage_logs")
    stats["total_usage"] = c.fetchone()[0]

    c.execute(
        f"SELECT COUNT(*) FROM usage_logs WHERE {_iran_today_condition('created_at')}"
    )
    stats["usage_today"] = c.fetchone()[0]

    c.execute(
        f"SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE {_iran_today_condition('created_at')}"
    )
    stats["active_users_today"] = c.fetchone()[0]

    conn.close()
    return stats


def delete_old_usage_logs(days=180):
    """حذف لاگ‌های قدیمی‌تر از تعداد روز مشخص (برای جلوگیری از بزرگ شدن دیتابیس)"""
    try:
        days = int(days)
    except (TypeError, ValueError):
        return False

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "DELETE FROM usage_logs WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.commit()
        return c.rowcount
    except Exception as e:
        print(f"❌ خطا در پاک‌سازی لاگ‌های قدیمی: {e}")
        return False
    finally:
        conn.close()


# ===== توابع تنظیمات =====
def set_setting(key, value):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
            (key, value),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در ذخیره تنظیمات: {e}")
        return False
    finally:
        conn.close()


def get_setting(key):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_all_settings():
    """دریافت همه تنظیمات"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    results = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in results}


# ===== توابع کمکی =====
def get_db_stats():
    """دریافت آمار کلی دیتابیس"""
    conn = get_db_connection()
    c = conn.cursor()

    stats = {}

    # تعداد کل درخواست‌ها
    c.execute("SELECT COUNT(*) FROM photo_requests")
    stats["total_requests"] = c.fetchone()[0]

    # تعداد کاربران منحصر به فرد
    c.execute("SELECT COUNT(DISTINCT user_id) FROM photo_requests")
    stats["unique_users"] = c.fetchone()[0]

    # تعداد ادمین‌ها
    c.execute("SELECT COUNT(*) FROM admins WHERE is_active = 1")
    stats["total_admins"] = c.fetchone()[0]

    # تعداد نظرسنجی‌ها
    c.execute("SELECT COUNT(*) FROM surveys")
    stats["total_surveys"] = c.fetchone()[0]

    # تعداد عکس‌های پیش‌آپلود
    c.execute("SELECT COUNT(*) FROM preuploaded_photos WHERE used = 0")
    stats["preuploaded_photos"] = c.fetchone()[0]

    conn.close()
    return stats


def init_admin_user():
    """اطمینان از ثبت سازنده/مالک ربات در لیست ادمین‌ها"""

    conn = get_db_connection()
    c = conn.cursor()

    for super_admin_id in SUPER_ADMIN_IDS:
        c.execute(
            """
            INSERT OR IGNORE INTO admins (user_id, added_by, is_active)
            VALUES (?, ?, 1)
        """,
            (super_admin_id, super_admin_id),
        )
        c.execute(
            "UPDATE admins SET is_active = 1 WHERE user_id = ?", (super_admin_id,)
        )
        print(f"✅ دسترسی کامل برای آیدی {super_admin_id} فعال است.")

    conn.commit()

    conn.close()


if __name__ == "__main__":
    init_db()
    init_admin_user()
    print("DATABASE SUCCESSFULLY CREATED.")
