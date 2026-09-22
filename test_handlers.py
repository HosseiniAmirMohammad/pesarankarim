#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تست: آیا callback handler برای claim_reward درست registered است؟
"""

import importlib.util
import os

BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "pesarankarim_test", os.path.join(BASE, "pesarankarim.py")
)
bot = importlib.util.module_from_spec(spec)


# Mock قبل از loading
class FakApp:
    def __init__(self):
        self.handlers = []

    def add_handler(self, handler):
        self.handlers.append(handler)
        print(f"✅ Handler اضافه شد: {handler}")


fake_app = FakApp()

# بگذار test کنیم اما app رو مسدود نکنیم
print("🔍 Parsing pesarankarim.py برای پیدا کردن handler registration...")

# بهتر است من directly search کنم
with open("pesarankarim.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# پیدا کردن تمام CallbackQueryHandler
callbacks = re.findall(
    r"CallbackQueryHandler\s*\(\s*(\w+)\s*,\s*pattern\s*=\s*([^)]+)\)", content
)

print("\n" + "=" * 60)
print("📊 Callback Handlers:")
print("=" * 60)

for func, pattern in callbacks:
    print(f"  ✅ Handler: {func}")
    print(f"     Pattern: {pattern}")

# بررسی claim_reward
print("\n" + "=" * 60)
print("🎯 بررسی claim_reward handler:")
print("=" * 60)

claim_reward_match = re.search(
    r"CallbackQueryHandler\s*\(\s*claim_reward_callback\s*,\s*pattern\s*=\s*([^)]+)\)",
    content,
)

if claim_reward_match:
    pattern = claim_reward_match.group(1)
    print(f"✅ claim_reward_callback با pattern registered:")
    print(f"   {pattern}")

    # test pattern
    import re as re_module

    pattern_str = pattern.strip("'\"`")  # Remove quotes
    test_cases = [
        "claim_reward|mashhad",
        "claim_reward|tehran",
        "back_to_menu",
        "other",
    ]
    print(f"\n   Pattern test:")
    for test_data in test_cases:
        if re_module.match(pattern_str, test_data):
            print(f"     ✅ '{test_data}' matches")
        else:
            print(f"     ❌ '{test_data}' does NOT match")
else:
    print("❌ claim_reward_callback handler NOT found!")

# بررسی handler order
print("\n" + "=" * 60)
print("📑 Handler Registration Order:")
print("=" * 60)

handler_lines = re.finditer(
    r"app\.add_handler\(CallbackQueryHandler\s*\(\s*(\w+)", content
)

order = list(handler_lines)
for i, match in enumerate(order, 1):
    handler_name = match.group(1)
    print(f"  {i}. {handler_name}")
    if handler_name == "claim_reward_callback":
        print(f"     👈 این اینجاست (position {i})")
