import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "pesarankarim.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

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
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_send_history_photo_request_id ON send_history(photo_request_id)"
    )

    conn.commit()
    conn.close()

    print("DATABASE SUCCESSFULY CREATED.")


def get_db_connection():
    return sqlite3.connect(DB_PATH)


# ===== توابع مدیریت ادمین =====
def add_admin(user_id, username=None, first_name=None, last_name=None, added_by=None):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT OR IGNORE INTO admins (user_id, username, first_name, last_name, added_by)
            VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, username, first_name, last_name, added_by or user_id),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR IN ADDING ADMIN:{e}")
        return False
    finally:
        conn.close()


def remove_admin(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"ERROR CANNOT ADD ADMIN: {e}")
        return False
    finally:
        conn.close()


def is_admin(user_id):
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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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


def is_super_admin(user_id):
    """بررسی سوپر ادمین بودن (اولین ادمین)"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT user_id FROM admins 
        WHERE user_id = ? AND is_active = 1 
        ORDER BY added_at ASC LIMIT 1
    """,
        (user_id,),
    )
    result = c.fetchone()
    conn.close()
    return result is not None


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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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

    conn.close()
    return stats


def init_admin_user():
    YOUR_USER_ID = 383415679

    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM admins")
    count = c.fetchone()[0]

    if count == 0:
        c.execute(
            """
            INSERT OR IGNORE INTO admins (user_id, added_by, is_active)
            VALUES (?, ?, 1)
        """,
            (YOUR_USER_ID, YOUR_USER_ID),
        )
        conn.commit()
        print(f"✅ ادمین اولیه با آیدی {YOUR_USER_ID} اضافه شد.")
    else:
        print("ℹ️ ادمین اولیه قبلاً اضافه شده است.")

    conn.close()


if __name__ == "__main__":
    init_db()
    init_admin_user()
    print("DATABASE SUCCESSFULLY CREATED.")
