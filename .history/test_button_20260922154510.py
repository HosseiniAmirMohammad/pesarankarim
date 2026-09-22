#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pesarankarim as bot

print("=" * 60)
print("🔍 بررسی دکمه «✅ نظر دادم»")
print("=" * 60)

# بررسی دکمه mashhad
kb = bot.review_done_kb("mashhad")
if kb and hasattr(kb, 'inline_keyboard'):
    print("\n✅ keyboard برای mashhad:")
    for i, row in enumerate(kb.inline_keyboard):
        for j, btn in enumerate(row):
            print(f"  [{i}][{j}] متن: '{btn.text}'")
            print(f"  [{i}][{j}] callback_data: '{btn.callback_data}'")
else:
    print("❌ keyboard برای mashhad None یا invalid")

# بررسی دکمه tehran
kb2 = bot.review_done_kb("tehran")
if kb2 and hasattr(kb2, 'inline_keyboard'):
    print("\n✅ keyboard برای tehran:")
    for i, row in enumerate(kb2.inline_keyboard):
        for j, btn in enumerate(row):
            print(f"  [{i}][{j}] متن: '{btn.text}'")
            print(f"  [{i}][{j}] callback_data: '{btn.callback_data}'")
else:
    print("❌ keyboard برای tehran None یا invalid")

# بررسی pattern
import re
pattern = r"^claim_reward(?:\|.*)?$"
print(f"\n📊 Pattern test:")
print(f"  Pattern: {pattern}")
test_data = ["claim_reward|mashhad", "claim_reward|tehran", "claim_reward", "other"]
for data in test_data:
    match = re.match(pattern, data)
    print(f"  '{data}': {'✅ MATCH' if match else '❌ NO MATCH'}")

# بررسی پیام اول
msg = bot.google_review_message("mashhad")
print(f"\n📝 پیام تشکر ({len(msg)} کاراکتر):")
print(f"  {msg[:150]}...")
