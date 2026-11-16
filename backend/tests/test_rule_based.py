# pyright: basic
"""pipeline/rule_based.py (규칙 기반 단독 = 팀원 잉크 농도 판독) 테스트.

양식(layout)대로 흰 캔버스에 동그라미 테두리와 채움 원을 그려서 가짜 정렬 이미지를 만들고, 팀원 판독(read_sheet)을 한 뒤
rule_based.verify_sheet() 가 같은 결과를 돌려주는지, [설정] 을 바꾸면 그 값으로 다시 판독하는지 확인한다.
(채움 원의 반지름으로 칸의 g·cov 를 맞춤: 안쪽 원(반지름의 70%)에서 g ≈ cov ≈ (원 반지름 / 안쪽 원 반지름)^2)

실행 (backend 폴더에서):  python -m unittest discover -s tests -t .
"""
import unittest
from unittest import mock

import cv2
import numpy as np

from pipeline import rule_based
from pipeline.read import ReadConfig, read_sheet
from sheetgen.layout import SheetSpec, compute_layout, mm_to_px

DPI = 200
W, H = 1654, 2339          # A4 세로, 200dpi


def make_sheet():
    """5문항 5지선다 세로형 양식과, 모든 동그라미 테두리만 그린 흰 이미지."""
    layout = compute_layout(SheetSpec(num_questions=5, num_choices=5, orientation="portrait"))
    img = np.full((H, W), 255, np.uint8)
    bubbles = [c for q in layout["mcq"]["questions"] for c in q["choices"]] + layout["student_id"]["bubbles"]
    for b in bubbles:
        cx, cy = (int(round(mm_to_px(v, DPI))) for v in b["center_mm"])
        cv2.circle(img, (cx, cy), int(round(mm_to_px(b["radius_mm"], DPI))), 0, 1)
    return layout, img


def fill(img, layout, q, choice, ratio):
    """문항 q(1부터)의 선지 choice(1부터)를 칠함. ratio 1 이상이면 안쪽 원 전체, 아니면 안쪽 원의 ratio 만큼(가운데 원)."""
    b = layout["mcq"]["questions"][q - 1]["choices"][choice - 1]
    cx, cy = (int(round(mm_to_px(v, DPI))) for v in b["center_mm"])
    inner = 0.7 * mm_to_px(b["radius_mm"], DPI)
    r = inner * 1.3 if ratio >= 1 else inner * np.sqrt(ratio)
    cv2.circle(img, (cx, cy), int(round(r)), 0, -1)


class RuleBased(unittest.TestCase):
    def setUp(self):
        self.layout, self.img = make_sheet()
        fill(self.img, self.layout, 1, 3, 1.0)        # 1번: 3번 선지 100%  → 마킹
        fill(self.img, self.layout, 2, 2, 0.40)       # 2번: 2번 선지 40%   → 애매 (cov 0.4 ≥ 0.25)
        fill(self.img, self.layout, 3, 1, 0.08)       # 3번: 1번 선지 8%    → 빈칸 (g < 0.10)
        fill(self.img, self.layout, 4, 2, 1.0)        # 4번: 2번·4번 선지 100% → 복수
        fill(self.img, self.layout, 4, 4, 1.0)
        fill(self.img, self.layout, 5, 1, 0.15)       # 5번: 1번 선지 15%   → 연한 회색 1개 = 흐린 마킹(답으로 인정)
        self.read = read_sheet(self.img, self.layout)           # 팀원 판독 (기본 = 잉크 농도 방식)

    def judge(self):
        return rule_based.verify_sheet(self.read, self.img, self.layout)

    def test_g_또는_cov_60퍼센트_이상은_마킹(self):
        q = self.judge()["mcq"][0]
        self.assertEqual((q["answer"], q["status"], q["needs_review"]), ([3], "ok", False))

    def test_cov_25퍼센트_이상_60퍼센트_미만은_애매_검수(self):
        q = self.judge()["mcq"][1]
        self.assertIsNone(q["answer"])
        self.assertEqual((q["status"], q["needs_review"], q["reason"]), ("ambiguous", True, "partial"))

    def test_g_10퍼센트_미만은_빈칸(self):
        q = self.judge()["mcq"][2]
        self.assertEqual((q["answer"], q["status"], q["needs_review"]), ([], "blank", False))

    def test_연한_칸_하나는_흐린_마킹으로_인정(self):
        q = self.judge()["mcq"][4]
        self.assertEqual((q["answer"], q["status"], q["reason"]), ([1], "ok", "faint"))

    def test_복수_마킹(self):
        q = self.judge()["mcq"][3]
        self.assertEqual((q["answer"], q["status"]), ([2, 4], "multi"))

    def test_기본_설정이면_팀원_판독_결과를_그대로_돌려줌(self):
        with mock.patch.object(rule_based, "read_sheet", side_effect=AssertionError("다시 판독하면 안 됨")):
            out = self.judge()
        self.assertEqual(out["mcq"], self.read["mcq"])
        self.assertEqual(out["student_id"], self.read["student_id"])
        self.assertEqual(out["rule_based"], {"method": "darkness", "solid_min": 0.60, "partial_min": 0.25,
                                             "light_min": 0.10, "ring_min": 0.15})

    def test_설정을_바꾸면_그_값으로_다시_판독(self):
        with mock.patch.object(rule_based, "SOLID_MIN", 0.35):            # cov 0.4 는 이제 마킹
            out = self.judge()
            self.assertEqual((out["mcq"][1]["answer"], out["mcq"][1]["status"]), ([2], "ok"))
            self.assertEqual(out["read_config"]["solid_min"], 0.35)
            self.assertEqual(out["rule_based"]["solid_min"], 0.35)
        with mock.patch.object(rule_based, "PARTIAL_MIN", 0.50):          # cov 0.4 는 이제 애매가 아니라 연한 칸 → 흐린 마킹
            q = self.judge()["mcq"][1]
            self.assertEqual((q["answer"], q["reason"]), ([2], "faint"))
        with mock.patch.object(rule_based, "LIGHT_MIN", 0.20):            # 15% 는 이제 연한 칸이 아니라 빈칸
            q = self.judge()["mcq"][4]
            self.assertEqual((q["answer"], q["status"]), ([], "blank"))

    def test_채움_비율_방식으로_판독된_read가_들어와도_잉크_농도로_다시_판독(self):
        old = read_sheet(self.img, self.layout, ReadConfig(method="fill"))
        out = rule_based.verify_sheet(old, self.img, self.layout)
        self.assertEqual(out["read_config"]["method"], "darkness")
        self.assertEqual(out["mcq"][0]["answer"], [3])

    def test_원본_read는_바뀌지_않음(self):
        import copy
        before = copy.deepcopy(self.read)
        self.judge()
        self.assertEqual(self.read, before)


if __name__ == "__main__":
    unittest.main()
