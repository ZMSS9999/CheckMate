# pyright: basic
"""CNN 단독 방식 — 규칙 기반 판독 값은 쓰지 않고, 모든 칸을 CNN으로만 판정.

[이 파일의 역할]
  - 검수 개수를 비교하려고 만든 "CNN 단독" 방식. flow.py 의 DUAL_VERIFY = "cnn_only" 로 고르면 실행됨
  - 객관식의 모든 선지 칸(과 학번의 모든 칸)을 잘라서 CNN이 8클래스로 분류
        정석 마킹 / 얇게 채움(반만 채움) / 체크 표시 / 동그라미 / 번짐 / 칸 삐져나옴  → 마킹된 칸
        빈칸 / 수정테이프                                                              → 마킹 아님
  - 규칙 기반 채움·잉크 농도 값(g, cov, ring)과 그 기준(solid_min 등)은 판정에 쓰지 않음.
    (v2 와 달리 채움이 높은 칸도 규칙 기반이 확정하지 않고 CNN이 판정함)
  - 문항 판정: 마킹된 칸들이 답 (0개 무응답 / 1개 정상 / 2개 이상 복수). 아래 경우는 그 문항(학번이면 그 자리)을 검수로 보냄
        1) CNN 클래스 신뢰도(예측 클래스의 softmax 확률)가 CONFIDENCE_MIN 미만인 칸이 있음
        2) 수정테이프로 분류된 칸이 있는데 그 문항에 마킹된 칸이 하나도 없음 (TAPE_WITHOUT_MARK_REVIEW)
  - 팀원 판독의 문항 단위 검수 사유(반사·과노출·신뢰도·애매 등)도 쓰지 않음. 사진 전체 재촬영 판정만 flow.py 가 이 앞에서 먼저 처리함

[설정] 아래 세 값은 dual_verify_v2/config.py 의 같은 이름 값과 같은 뜻이고 기본값도 같음 (v2 와 같은 조건으로 비교하려고)

[입력 → 출력]
  verify_sheet(read, warped, layout)
    read   : 팀원 판독 결과 (칸 위치 보정값 offsets_mm 과 해상도 read_config["dpi"] 만 가져다 씀)
    warped : P1 정렬 이미지 (200dpi 정면 이미지)
    layout : 양식 좌표 dict
    → read 의 복사본에 판정 결과를 덮어써서 돌려줌 (dual_verify_v2 와 같은 형식)
        read["mcq"][i]  : answer, status(ok / blank / multi / review), needs_review, reason(""/"cnn_low_conf"/"cnn_tape_no_mark"),
                          dual(선지별 CNN 클래스·신뢰도·검수 사유)
        read["student_id"]["digits"][i] : value, status, reason, dual → 학번 text / raw / status 도 다시 계산
        read["summary"] : status_counts, needs_review 다시 계산, "cnn_only": {"checked", "review_questions", "review_digits"}
        read["cnn_only"]: 사용한 설정값 표식
    ※ read["mcq"][i]["fill"](막대 표시용 채움 값)은 팀원 판독 값 그대로 남음. 판정에는 안 쓰임

[사용 예]
  from pipeline import cnn_only
  read2 = cnn_only.verify_sheet(read, warped, layout)                      # 기본 CNN 사용
  read2 = cnn_only.verify_sheet(read, warped, layout, classifier=my_fn)    # 테스트: 가짜 분류기
    (my_fn: 칸 이미지 목록 → [(클래스 번호, 신뢰도), ...])
"""
from __future__ import annotations

import copy
from typing import Any

import cv2
import numpy as np

# CNN 분류기·칸 자르기·클래스 구분은 dual_verify_v2 와 같은 것을 씀 (같은 가중치로 비교하기 위해)
from dual_verify_v2 import _column_offsets, _crop_bubble, _default_classifier, _status_of
from dual_verify_v2.compare import judge_question

# ======================================================================================
# [설정] 여기만 고치면 됨
# ======================================================================================
CONFIDENCE_MIN = 0.9
"""CNN 클래스 신뢰도 임계값 (0~1). 이 값 미만인 칸이 있으면 그 문항(자리)은 검수.
   올리면 검수가 늘고, 내리면 검수가 줄지만 오판독 위험이 커짐."""

TAPE_WITHOUT_MARK_REVIEW = True
"""True: 수정테이프로 분류된 칸이 있는데 그 문항에 마킹된 선지가 하나도 없으면 검수. False: 이 규칙을 쓰지 않음."""

INCLUDE_STUDENT_ID = True
"""True: 학번 칸도 CNN으로 판정. False: 객관식만 판정하고 학번은 팀원 판독 결과를 그대로 둠."""
# ======================================================================================

__all__ = ["verify_sheet"]


def verify_sheet(read: dict[str, Any], warped: np.ndarray, layout: dict[str, Any],
                 classifier: Any = None) -> dict[str, Any]:
    """객관식·학번의 모든 칸을 CNN으로만 판정. 원본 read 는 바꾸지 않고 복사본을 돌려줌.

    매개변수:
        read: 팀원 판독 결과 (offsets_mm, read_config["dpi"] 사용)
        warped: P1 정렬 이미지 (BGR 3채널 또는 흑백)
        layout: 양식 좌표 dict
        classifier: 칸 이미지 목록 → [(클래스 번호, 신뢰도)] 함수. None이면 학습된 CnnClassifier(기본 가중치)를 불러 씀
    반환:
        판정 결과가 반영된 read 복사본 (모듈 설명의 [입력 → 출력] 참고)
    예외:
        FileNotFoundError: classifier 가 None인데 가중치 파일이 없을 때
        ValueError: 분류 결과 수가 칸 수와 다를 때
    """
    if classifier is None:
        classifier = _default_classifier()

    out = copy.deepcopy(read)
    dpi = int(out["read_config"]["dpi"])
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if warped.ndim == 3 else warped
    offsets = out.get("offsets_mm")

    # 1) 판정 단위(객관식 문항 하나 / 학번 자리 하나)를 모음
    groups: list[dict[str, Any]] = []
    q_by_no = {q["q"]: q for q in layout["mcq"]["questions"]}
    shift = _column_offsets(layout, offsets)
    for rq in out["mcq"]:
        bs = q_by_no[rq["q"]]["choices"]
        groups.append({"kind": "mcq", "ref": rq, "bubbles": bs, "nos": [c["choice"] for c in bs],
                       "shift": shift.get(rq["q"], (0.0, 0.0))})
    digits = out.get("student_id", {}).get("digits") or []
    if INCLUDE_STUDENT_ID and digits and layout.get("student_id"):
        sdx, sdy = (offsets or {}).get("student_id") or (0.0, 0.0)
        for d in digits:
            bs = sorted((b for b in layout["student_id"]["bubbles"] if b["digit_index"] == d["digit_index"]),
                        key=lambda b: b["value"])
            groups.append({"kind": "digit", "ref": d, "bubbles": bs, "nos": [b["value"] for b in bs],
                           "shift": (sdx, sdy)})

    # 2) 모든 칸을 잘라서 한 번에 CNN으로 분류 (규칙 기반 값으로 건너뛰는 칸이 없음)
    crops: list[np.ndarray] = []
    spans: list[tuple[int, int]] = []
    for g in groups:
        start = len(crops)
        crops += [_crop_bubble(gray, b, g["shift"][0], g["shift"][1], dpi) for b in g["bubbles"]]
        spans.append((start, len(crops)))
    results = classifier(crops)
    if len(results) != len(crops):
        raise ValueError(f"분류 결과 수({len(results)})가 칸 수({len(crops)})와 다릅니다")

    # 3) 판정 단위별로 통과 / 검수 결정해서 read 에 반영
    #    judge_question 은 채움 값 ≥ 기준이면 규칙 기반 마킹으로 보므로, 채움 0.0 · 기준 1.0 을 넘겨 모든 칸이 CNN 판정이 되게 함
    review_questions: list[int] = []
    review_digits: list[int] = []
    for g, (a, b) in zip(groups, spans):
        preds = results[a:b]
        v = judge_question([0.0] * len(preds), preds, 1.0, CONFIDENCE_MIN, g["nos"], TAPE_WITHOUT_MARK_REVIEW)
        ref = g["ref"]
        ref["dual"] = v
        why = "" if v["ok"] else ("cnn_tape_no_mark" if v["reasons"][0]["type"] == "tape_no_mark" else "cnn_low_conf")
        if g["kind"] == "mcq":
            if v["ok"]:
                ref["answer"], ref["status"], ref["needs_review"] = v["answer"], _status_of(v["answer"]), False
            else:
                ref["answer"], ref["status"], ref["needs_review"] = None, "review", True
                review_questions.append(ref["q"])
        else:
            if v["ok"]:
                ref["value"], ref["status"] = v["answer"], _status_of(v["answer"])
            else:
                ref["value"], ref["status"] = None, "review"
                review_digits.append(ref["digit_index"])
        ref["reason"] = why

    # 4) 학번 text / raw / status 를 자리 결과로 다시 계산 (read.py 의 학번 규칙과 같음: 모든 자리가 정상이어야 확정)
    if any(g["kind"] == "digit" for g in groups):
        sid = out["student_id"]
        raw = "".join(str(d["value"][0]) if d["status"] == "ok" and d["value"] else "?" for d in digits)
        statuses = {d["status"] for d in digits}
        status = "ok" if statuses == {"ok"} else "blank" if statuses == {"blank"} else "review"
        sid.update({"raw": raw, "text": raw if status == "ok" else None,
                    "status": status, "needs_review": status != "ok"})

    # 5) 요약 다시 계산
    counts: dict[str, int] = {}
    for rq in out["mcq"]:
        counts[rq["status"]] = counts.get(rq["status"], 0) + 1
    out["summary"]["status_counts"] = counts
    out["summary"]["needs_review"] = (out["student_id"]["needs_review"]
                                      or any(rq["needs_review"] for rq in out["mcq"]))
    out["summary"]["cnn_only"] = {"checked": len(out["mcq"]), "review_questions": review_questions,
                                  "review_digits": review_digits}
    out["cnn_only"] = {"confidence_min": CONFIDENCE_MIN, "tape_without_mark_review": TAPE_WITHOUT_MARK_REVIEW,
                       "include_student_id": INCLUDE_STUDENT_ID}
    return out
