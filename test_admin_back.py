import unittest

from pesarankarim import BTN_ADMIN_BACK, BTN_ADMIN_BACK_TEXT


class AdminBackButtonTests(unittest.TestCase):
    def test_admin_back_button_matches_text(self):
        self.assertEqual(BTN_ADMIN_BACK_TEXT, "🔙 بازگشت به منو")
        self.assertEqual(BTN_ADMIN_BACK.text, BTN_ADMIN_BACK_TEXT)


if __name__ == "__main__":
    unittest.main()
