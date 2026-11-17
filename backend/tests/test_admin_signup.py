# pyright: basic
"""관리자 회원가입(새 관리자 계정 바로 만들기) 테스트. 임시 폴더의 계정 파일을 쓰므로 실제 계정은 건드리지 않음.

실행 (backend 폴더에서):  python -m unittest discover -s tests -t .
"""
import os
import tempfile
import unittest
from unittest import mock

from app import accounts


class SignupAdmin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(accounts, "USERS_PATH", os.path.join(self.tmp.name, "users.json")),
                        mock.patch.object(accounts, "SECRET_PATH", os.path.join(self.tmp.name, "secret.key"))]
        for p in self.patches:
            p.start()
        accounts.setup_first_admin("admin01", "관리자1", "admin-pass-1")

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_새_관리자_계정이_만들어지고_로그인됨(self):
        u = accounts.signup_admin("admin02", "관리자2", "new-pass-123")
        self.assertEqual((u["username"], u["role"], u["active"]), ("admin02", "admin", True))
        self.assertNotIn("pw_hash", u)
        self.assertFalse(u["must_change"])                               # 임시 비밀번호가 아니라 직접 정한 비밀번호
        self.assertEqual(accounts.authenticate("admin02", "new-pass-123")["role"], "admin")

    def test_이름을_비우면_아이디가_이름(self):
        self.assertEqual(accounts.signup_admin("admin02", "", "new-pass-123")["name"], "admin02")

    def test_아이디_중복_형식_오류_짧은_비밀번호는_거절(self):
        with self.assertRaisesRegex(accounts.AccountError, "이미"):
            accounts.signup_admin("admin01", "x", "new-pass-123")
        with self.assertRaises(accounts.AccountError):
            accounts.signup_admin("A!", "x", "new-pass-123")
        with self.assertRaises(accounts.AccountError):
            accounts.signup_admin("admin02", "x", "short")
        self.assertIsNone(accounts.get_user("admin02"))

    def test_기존_계정은_바뀌지_않음(self):
        before = accounts.get_user("admin01")
        accounts.signup_admin("admin02", "관리자2", "new-pass-123")
        self.assertEqual(accounts.get_user("admin01"), before)


if __name__ == "__main__":
    unittest.main()
