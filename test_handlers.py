                     
                       
"""
تست: آیا callback handler برای claim_reward درست registered است؟
"""

import ast
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(BASE, "pesarankarim.py")
with open(SOURCE_PATH, "r", encoding="utf-8") as f:
    source = f.read()

module = ast.parse(source, filename=SOURCE_PATH)

handlers = []
for node in ast.walk(module):
    if not isinstance(node, ast.Call):
        continue
    if not isinstance(node.func, ast.Name):
        continue
    if node.func.id != "CallbackQueryHandler":
        continue

    func_name = None
    pattern = None
    if node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Name):
            func_name = first_arg.id

    for keyword in node.keywords:
        if keyword.arg == "pattern":
            try:
                pattern = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError):
                pattern = None
            break

    if func_name is not None:
        handlers.append((func_name, pattern))

print("🔍 Parsing pesarankarim.py برای پیدا کردن handler registration...")
print("\n" + "=" * 60)
print("📊 Callback Handlers:")
print("=" * 60)

for func_name, pattern in handlers:
    print(f"  ✅ Handler: {func_name}")
    print(f"     Pattern: {pattern}")

print("\n" + "=" * 60)
print("🎯 بررسی claim_reward handler:")
print("=" * 60)

claim_pattern = next(
    (
        pattern
        for func_name, pattern in handlers
        if func_name == "claim_reward_callback"
    ),
    None,
)
if claim_pattern is None:
    raise AssertionError("claim_reward_callback handler NOT found!")

print(f"✅ claim_reward_callback با pattern registered:")
print(f"   {claim_pattern}")

for test_data in [
    "claim_reward|mashhad",
    "claim_reward|tehran",
    "back_to_menu",
    "other",
]:
    match = re.fullmatch(claim_pattern, test_data)
    if match:
        print(f"     ✅ '{test_data}' matches")
    else:
        print(f"     ❌ '{test_data}' does NOT match")

assert re.fullmatch(claim_pattern, "claim_reward|mashhad")
assert re.fullmatch(claim_pattern, "claim_reward|tehran")
assert not re.fullmatch(claim_pattern, "back_to_menu")
assert not re.fullmatch(claim_pattern, "other")

# Regression check: branch values may arrive in Persian/variant forms.
# This must still resolve to the correct Google review URL for each branch.
try:
    from pesarankarim import google_map_link, normalize_branch_name
except Exception as exc:  # pragma: no cover - test should fail clearly if import is broken
    raise AssertionError(f"Importing branch helpers failed: {exc}")

assert normalize_branch_name("tehran") == "tehran"
assert normalize_branch_name("Tehran") == "tehran"
assert normalize_branch_name("تهران") == "tehran"
assert normalize_branch_name("mashhad") == "mashhad"
assert normalize_branch_name("مشهد") == "mashhad"
assert google_map_link("tehran") == "https://search.google.com/local/writereview?placeid=ChIJsTjtDAAHjj8RIeGyvM4NXFs"
assert google_map_link("تهران") == "https://search.google.com/local/writereview?placeid=ChIJsTjtDAAHjj8RIeGyvM4NXFs"
assert google_map_link("مشهد") == "https://search.google.com/local/writereview?placeid=ChIJ3YrapemRbD8RM2d30ngNSig"

print("\n" + "=" * 60)
print("📑 Handler Registration Order:")
print("=" * 60)

order = []
for node in ast.walk(module):
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_handler"
    ):
        if node.args and isinstance(node.args[0], ast.Call):
            inner = node.args[0]
            if (
                isinstance(inner.func, ast.Name)
                and inner.func.id == "CallbackQueryHandler"
            ):
                if inner.args and isinstance(inner.args[0], ast.Name):
                    order.append(inner.args[0].id)

for i, handler_name in enumerate(order, 1):
    print(f"  {i}. {handler_name}")
    if handler_name == "claim_reward_callback":
        print(f"     👈 این اینجاست (position {i})")

assert order.index("claim_reward_callback") > order.index("usage_log_callback")
