#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تست شبیه‌سازی callback: بررسی اینکه claim_reward_callback چه می‌کند
"""
import asyncio
import types
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import bot
import pesarankarim as bot

async def test_claim_reward():
    """شبیه‌سازی کامل claim_reward_callback"""
    
    print("=" * 70)
    print("🧪 تست: claim_reward_callback Simulation")
    print("=" * 70)
    
    # ساخت fake update و context
    user_id = 12345
    
    fake_query = AsyncMock()
    fake_query.from_user = types.SimpleNamespace(id=user_id, first_name="TestUser")
    fake_query.data = "claim_reward|mashhad"
    fake_query.answer = AsyncMock()
    fake_query.edit_message_reply_markup = AsyncMock()
    
    fake_update = types.SimpleNamespace(
        callback_query=fake_query,
    )
    
    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock()
    
    fake_context = types.SimpleNamespace(
        bot=fake_bot,
        user_data={},
    )
    
    print(f"\n📍 شروع test:")
    print(f"  User ID: {user_id}")
    print(f"  Callback data: {fake_query.data}")
    
    try:
        print(f"\n📞 فراخوانی claim_reward_callback...")
        await bot.claim_reward_callback(fake_update, fake_context)
        print(f"✅ claim_reward_callback بدون خطا اجرا شد")
        
        # بررسی calls
        print(f"\n📊 Calls:")
        print(f"  query.answer calls: {fake_query.answer.await_count}")
        print(f"  query.edit_message_reply_markup calls: {fake_query.edit_message_reply_markup.await_count}")
        print(f"  bot.send_message calls: {fake_bot.send_message.await_count}")
        
        if fake_bot.send_message.await_count > 0:
            print(f"\n✅ پیام‌ها ارسال شدند:")
            for i, call in enumerate(fake_bot.send_message.await_args_list, 1):
                args, kwargs = call
                msg_text = kwargs.get('text', '')[:50] if 'text' in kwargs else 'N/A'
                print(f"  {i}. {msg_text}...")
        else:
            print(f"\n❌ هیچ پیام ارسال نشد!")
            
    except Exception as e:
        print(f"❌ Exception رخ داد:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

# Run async test
if __name__ == "__main__":
    asyncio.run(test_claim_reward())
