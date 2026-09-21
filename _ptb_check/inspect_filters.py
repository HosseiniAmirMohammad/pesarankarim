"""بررسی فیلترهای موجود در نسخه 21.9 کتابخانه python-telegram-bot"""
import re
import zipfile

WHEEL = r"_ptb_check\python_telegram_bot-21.9-py3-none-any.whl"
z = zipfile.ZipFile(WHEEL)

target = [n for n in z.namelist() if "filter" in n.lower()]
print("filter modules:", target)

source = z.read(target[0]).decode("utf-8")

for cls in ("class Document", "class Animation", "class Video", "class Photo", "class ChatType"):
    index = source.find(cls)
    print("\n=====", cls, "FOUND" if index > 0 else "MISSING")
    if index > 0:
        segment = source[index : index + 6000]
        names = re.findall(r"^\s{4}(\w+)\s*[:=]", segment, re.M)
        print(names)
