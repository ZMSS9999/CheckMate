# pyright: basic
"""pipeline/cnn_only.py (CNN 단독) 테스트: 가짜 분류기로 read dict 가 어떻게 바뀌는지 확인 (실제 CNN 불필요).

실행 (backend 폴더에서):  python -m unittest discover -s tests -t .
"""
import copy
import unittest
from unittest import mock

import numpy as np

from dual_verify_v2.config import BLANK as B, CHECK, CIRCLE, OVERFLOW, SMUDGE, STANDARD as S, TAPED as T, THIN
from dual_verify_v2.tests.test_verify_sheet import add_sid_read, fake, make_layout, make_read
from pipeline import cnn_only

OK = (B, 0.99)          # CNN: 빈칸, 확신 높음


class CnnOnly(unittest.TestCase):
    def setUp(self):
        self.layout = make_layout(n_q=2)
        self.img = np.full((400, 400), 255, np.uint8)

    def run_verify(self, read, grid):
        return cnn_only.verify_sheet(read, self.img, self.layout, classifier=fake(grid))

    def test_모든_칸을_CNN에_보냄(self):
        read = make_read([[0.9, 0, 0], [0, 0, 0]])                      # fake 가 칸 수(2문항 × 3 = 6칸)를 검사함
        out = self.run_verify(read, [[OK, OK, OK], [OK, OK, OK]])
        self.assertEqual([q["answer"] for q in out["mcq"]], [[], []])

    def test_마킹_6종은_마킹으로_판정(self):
        for cls in (S, THIN, CHECK, CIRCLE, SMUDGE, OVERFLOW):
            with self.subTest(cls=cls):
                out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), [[OK, (cls, 0.95), OK], [OK, OK, OK]])
                self.assertEqual((out["mcq"][0]["answer"], out["mcq"][0]["status"]), ([2], "ok"))
                self.assertFalse(out["mcq"][0]["needs_review"])

    def test_빈칸과_수정테이프는_마킹_아님(self):
        out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), [[OK, OK, (S, 0.97)], [(T, 0.98), OK, (S, 0.97)]])
        self.assertEqual([q["answer"] for q in out["mcq"]], [[3], [3]])   # 수정테이프 칸이 있어도 다른 칸에 마킹이 있으면 통과

    def test_규칙기반_채움값은_판정에_쓰이지_않음(self):
        read = make_read([[0.95, 0.9, 0], [0, 0, 0]])                   # 채움은 높지만 CNN은 모두 빈칸으로 봄
        out = self.run_verify(read, [[OK, OK, OK], [OK, OK, OK]])
        self.assertEqual((out["mcq"][0]["answer"], out["mcq"][0]["status"], out["mcq"][0]["needs_review"]),
                         ([], "blank", False))
        read = make_read([[0, 0, 0], [0, 0, 0]])                        # 반대로 채움은 0이지만 CNN이 마킹으로 봄
        out = self.run_verify(read, [[(S, 0.99), OK, OK], [OK, OK, OK]])
        self.assertEqual(out["mcq"][0]["answer"], [1])

    def test_복수_마킹은_둘다_답(self):
        out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), [[(S, .99), OK, (THIN, .95)], [OK, OK, OK]])
        self.assertEqual((out["mcq"][0]["answer"], out["mcq"][0]["status"]), ([1, 3], "multi"))

    def test_신뢰도_미만이면_그_문항만_검수(self):
        out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), [[OK, OK, (B, 0.85)], [OK, OK, OK]])
        q = out["mcq"][0]
        self.assertIsNone(q["answer"])
        self.assertEqual((q["status"], q["needs_review"], q["reason"]), ("review", True, "cnn_low_conf"))
        self.assertFalse(out["mcq"][1]["needs_review"])
        self.assertEqual(out["summary"]["cnn_only"]["review_questions"], [1])
        self.assertTrue(out["summary"]["needs_review"])

    def test_신뢰도가_임계값과_같으면_통과_설정을_바꾸면_따라감(self):
        grid = [[(B, 0.90), OK, OK], [(B, 0.85), OK, OK]]
        out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), grid)
        self.assertEqual([q["needs_review"] for q in out["mcq"]], [False, True])
        with mock.patch.object(cnn_only, "CONFIDENCE_MIN", 0.80):
            out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), grid)
            self.assertEqual([q["needs_review"] for q in out["mcq"]], [False, False])
            self.assertEqual(out["cnn_only"]["confidence_min"], 0.80)

    def test_수정테이프만_있고_마킹이_없으면_검수(self):
        grid = [[OK, (T, 0.98), OK], [OK, OK, OK]]
        out = self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), grid)
        self.assertEqual((out["mcq"][0]["needs_review"], out["mcq"][0]["reason"]), (True, "cnn_tape_no_mark"))
        with mock.patch.object(cnn_only, "TAPE_WITHOUT_MARK_REVIEW", False):
            self.assertFalse(self.run_verify(make_read([[0, 0, 0], [0, 0, 0]]), grid)["mcq"][0]["needs_review"])

    def test_팀원_판독의_보류_사유는_쓰지_않고_CNN이_다시_판정(self):
        read = make_read([[0, 0, 0], [0, 0, 0]], statuses={1: "ambiguous"})
        read["mcq"][0]["reason"] = "glare"                              # 팀원 판독이 반사로 검수 보냈어도 CNN 단독은 CNN 결과만 봄
        out = self.run_verify(read, [[OK, (S, .99), OK], [OK, OK, OK]])
        self.assertEqual((out["mcq"][0]["answer"], out["mcq"][0]["needs_review"], out["mcq"][0]["reason"]), ([2], False, ""))

    def test_원본_read는_바뀌지_않음(self):
        read = make_read([[0.9, 0, 0], [0, 0, 0]])
        before = copy.deepcopy(read)
        self.run_verify(read, [[OK, OK, (B, 0.5)], [OK, OK, OK]])
        self.assertEqual(read, before)

    def test_분류_결과_수가_다르면_예외(self):
        with self.assertRaises(ValueError):
            cnn_only.verify_sheet(make_read([[0, 0, 0], [0, 0, 0]]), self.img, self.layout, classifier=lambda crops: [OK])


class CnnOnlyStudentId(unittest.TestCase):
    def setUp(self):
        self.layout = make_layout(n_q=1, with_sid=True)
        self.img = np.full((700, 700), 255, np.uint8)

    def base(self, picks):
        return add_sid_read(make_read([[0, 0, 0]]), picks)

    def sid_grid(self, picks, override=None):
        """학번 자리별 CNN 결과(모든 칸): 고른 숫자는 정석 마킹, 나머지는 빈칸. override={(자리, 숫자): 결과}"""
        grid = []
        for di, p in enumerate(picks):
            row = [(S, 0.99) if v == p else OK for v in range(10)]
            for (edi, ev), res in (override or {}).items():
                if edi == di:
                    row[ev] = res
            grid.append(row)
        return grid

    def run_verify(self, read, picks, override=None):
        grid = [[OK, OK, OK]] + self.sid_grid(picks, override)
        return cnn_only.verify_sheet(read, self.img, self.layout, classifier=fake(grid))

    def test_학번도_모든_칸을_CNN으로_판정(self):
        out = self.run_verify(self.base([None, None]), [1, 2])          # 팀원 판독은 무응답이었지만 CNN 결과로 학번이 읽힘
        self.assertEqual(out["student_id"]["text"], "12")
        self.assertEqual(out["student_id"]["status"], "ok")
        self.assertFalse(out["summary"]["needs_review"])

    def test_학번_신뢰도_미만이면_그_자리만_검수(self):
        out = self.run_verify(self.base([1, 2]), [1, 2], override={(1, 5): (B, 0.8)})
        self.assertIsNone(out["student_id"]["text"])
        self.assertEqual(out["student_id"]["raw"], "1?")
        self.assertEqual(out["summary"]["cnn_only"]["review_digits"], [1])
        self.assertTrue(out["summary"]["needs_review"])

    def test_INCLUDE_STUDENT_ID를_끄면_학번은_그대로(self):
        read = self.base([1, 2])
        before = copy.deepcopy(read["student_id"])
        with mock.patch.object(cnn_only, "INCLUDE_STUDENT_ID", False):
            out = cnn_only.verify_sheet(read, self.img, self.layout, classifier=fake([[OK, OK, OK]]))
        self.assertEqual(out["student_id"], before)


if __name__ == "__main__":
    unittest.main()
