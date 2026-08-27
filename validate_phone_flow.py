import importlib.util, types, asyncio
spec = importlib.util.spec_from_file_location('mod', r'c:\Users\Amirinteraction\Desktop\pesarankarim\pesarankarim.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.real_member = lambda context, user_id: True
mod.save_photo_request = lambda **kwargs: None
mod.get_preuploaded_photo = lambda *args, **kwargs: None
mod.mark_preuploaded_as_used = lambda *args, **kwargs: None

print('normalize', mod.normalize_phone_number('09123456789'))
print('valid1', mod.is_valid_phone_number('09123456789'))
print('valid2', mod.is_valid_phone_number('9123456789'))
print('valid3', mod.is_valid_phone_number('+989123456789'))

class User: pass
class Msg: pass

async def run_case(v):
    u = User(); u.id = 1; u.first_name = 'A'
    msg = Msg(); msg.text = v; msg.reply_text = lambda *args, **kwargs: print('reply:', args[0])
    update = types.SimpleNamespace(effective_user=u, message=msg)
    context = types.SimpleNamespace(user_data={'photo_branch':'mashhad','photo_step':'phone','photo_code':'1234','photo_date':'1404/01/01'}, bot=types.SimpleNamespace(send_photo=lambda **kwargs: None, send_document=lambda **kwargs: None, delete_message=lambda **kwargs: None))
    await mod.handle_all_messages(update, context)
    print('CASE', v, '=> step=', context.user_data.get('photo_step'), 'phone=', context.user_data.get('photo_phone'))

asyncio.run(run_case('09123456789'))
asyncio.run(run_case('9123456789'))
asyncio.run(run_case('+989123456789'))
