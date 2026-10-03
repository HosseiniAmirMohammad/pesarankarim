from pesarankarim import BTN_ADMIN_BACK, BTN_ADMIN_BACK_TEXT


def test_admin_back_button_matches_text():
    assert BTN_ADMIN_BACK_TEXT == "🔙 بازگشت به منو"
    assert BTN_ADMIN_BACK.text == BTN_ADMIN_BACK_TEXT
