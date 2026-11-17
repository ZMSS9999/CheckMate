# pyright: basic
"""규칙 기반 판독 단독 방식 (CNN 없음) — 팀원의 잉크 농도 판독(method="darkness")으로만 판정.

[이 파일의 역할]
  - 검수 개수를 비교하려고 만든 "규칙 기반 단독" 방식. flow.py 의 DUAL_VERIFY = "rule_based" 로 고르면 실행됨
  - 칸 판독은 pipeline/read.py 의 잉크 농도 방식 그대로 (인쇄 마스크 → 칸마다 g·cov·ring → 칸 상태 → 문항 판정)
        g(안쪽 원 평균 잉크 농도) 또는 cov(안쪽 원 진한 픽셀 비율) ≥ SOLID_MIN(0.60)   → 마킹
        cov ≥ PARTIAL_MIN(0.25)                                                      → 애매(얇게 채움·체크) → 검수
        g ≥ LIGHT_MIN(0.10)                                                          → 연한 회색(흐림·지운 흔적)
        ring ≥ RING_MIN(0.15)                                                        → 동그라미 표시 → 검수
        그 외                                                                         → 빈칸
  - 과노출·반사 검수, 문항 신뢰도 등 팀원 판독의 나머지 기능도 그대로 적용됨 (read.py 의 ReadConfig 값)
  - CNN 은 쓰지 않음

[동작 방식]
  flow.py 가 팀원의 판독(P3)을 한 뒤 이 파일의 verify_sheet() 를 부름.
  아래 [설정] 값이 판독 결과에 이미 쓰인 값(기본값)과 같으면 그 결과를 그대로 돌려주고("rule_based" 표식만 덧붙임),
  하나라도 다르면 같은 정렬 이미지·양식으로 [설정] 값을 넣어 다시 판독해서 돌려줌
  → 기본값이면 DUAL_VERIFY = None(팀원 판독 단독)과 결과가 같고, [설정] 을 바꾸면 임계값만 다르게 비교해 볼 수 있음

[입력 → 출력]
  verify_sheet(read, warped, layout)
    read   : 팀원 판독 결과 (read_config 의 설정을 이어서 씀)
    warped : P1 정렬 이미지 (200dpi 정면 이미지)
    layout : 양식 좌표 dict
    → read_sheet(method="darkness") 형식의 read dict. 맨 위에 "rule_based": {"method", "solid_min", ...} 표식이 덧붙음

[사용 예]
  from pipeline import rule_based
  read2 = rule_based.verify_sheet(read, warped, layout)
"""
from __future__ import annotations

import copy
from dataclasses import fields, replace
from typing import Any

import numpy as np

from pipeline.read import ReadConfig, read_sheet

# ======================================================================================
# [설정] 여기만 고치면 됨 (ReadConfig 의 같은 이름 값과 같은 뜻, 기본값도 같음)
# ======================================================================================
SOLID_MIN = 0.60      # g 또는 cov 가 이 값 이상이면 마킹
PARTIAL_MIN = 0.25    # cov 가 이 값 이상이면 애매(얇게 채움·체크) → 검수
LIGHT_MIN = 0.10      # g 가 이 값 이상이면 연한 회색(흐림·지운 흔적)
RING_MIN = 0.15       # ring 이 이 값 이상이면 동그라미 표시 → 검수
# ======================================================================================

__all__ = ["verify_sheet"]


def _thresholds() -> dict[str, float]:
    """[설정] 의 임계값을 ReadConfig 필드 이름으로 묶은 dict."""
    return {"solid_min": SOLID_MIN, "partial_min": PARTIAL_MIN, "light_min": LIGHT_MIN, "ring_min": RING_MIN}


def verify_sheet(read: dict[str, Any], warped: np.ndarray, layout: dict[str, Any],
                 classifier: Any = None) -> dict[str, Any]:
    """팀원 잉크 농도 판독만으로 판정한 결과를 돌려줌. 원본 read 는 바꾸지 않음.

    매개변수:
        read: 팀원 판독 결과. read["read_config"] 의 값(해상도, 과노출·반사 기준 등)을 이어서 씀
        warped: P1 정렬 이미지 (임계값이 달라서 다시 판독할 때만 사용)
        layout: 양식 좌표 dict (위와 같음)
        classifier: 쓰지 않음 (flow.py 가 이중 검증 모듈과 같은 형식으로 부르기 때문에 받기만 함)
    반환:
        잉크 농도 방식 read dict + "rule_based" 표식
    """
    rc = read.get("read_config") or {}
    th = _thresholds()
    if rc.get("method") == "darkness" and all(rc.get(k) == v for k, v in th.items()):
        out = copy.deepcopy(read)                    # 이미 같은 설정으로 판독됨 → 다시 계산하지 않음
    else:
        names = {f.name for f in fields(ReadConfig)}
        base = ReadConfig(**{k: v for k, v in rc.items() if k in names})
        out = read_sheet(warped, layout, replace(base, method="darkness", **th))
    out["rule_based"] = {"method": "darkness", **th}
    return out
