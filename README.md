# CheckMate — AI 기반 시험 답안지 자동 채점 시스템

현재 들어 있는 것: **답안지 PDF 생성기 + 양식 좌표 저장 + 웹 입력 화면** (로드맵 2-1),
**ArUco·QR 정렬** (2-2), **규칙 기반 마킹 판독** (2-3), **정답표 입력·채점·엑셀 출력** (2-4),
인쇄 없이 전체 흐름을 검증하는 **가상 촬영 테스트**.
2026-11 추가: **잉크 농도 판독**(기본 판독 방식 변경), **로그인·계정·시험별 권한**, **문항 범위 담당**(통합 시험),
**관리자 화면**, **검수 화면 좌우 배치**(왼쪽 사진, 오른쪽 문항 확인).

3주차 회의 결정사항을 반영함.
- 객관식 **문항 수 5~45**, **선지 수 2~5** (1 단위로 웹에서 선택)
- 주관식 **5문항 고정** (단답형~한 문장)
- 시험지에는 **이름·학번만** 기입, **시험명·과목명은 QR코드**에 저장
- **세로 / 가로** 양식 두 가지
- JSON 항목명 `template_id`, `template_version`

## 폴더 구조

```
checkmate/
├── frontend/
│   └── index.html            # 웹 화면 전체 (로그인, 시험 단계 1~5, 관리자 화면. HTML+JS 한 파일, 빌드 없음)
└── backend/
    ├── app/
    │   ├── main.py           # FastAPI: API + frontend 제공, 로그인 확인·권한 검사
    │   ├── service.py        # 답안지 생성·저장 로직 (웹과 분리, 테스트에서도 사용)
    │   ├── grading_service.py # 정답표 저장(범위별 입력 포함) → 사진 판독 → 검수 수정 → 채점 → 엑셀 (웹·명령행 공용)
    │   ├── accounts.py       # 계정·로그인: users.json, 비밀번호 해시, 로그인 토큰(secret.key로 서명)
    │   ├── access.py         # 시험별 권한: 소유자·참여자(manager/review/view), 문항 범위 담당 (access.json)
    │   └── admin_service.py  # 관리자 화면: 전체 시험 현황·목록 엑셀, 양식 목록, 시스템 설정(settings.json)
    ├── sheetgen/
    │   ├── frame.py          # 방향별 고정 규격 (마커 ID·위치, QR 위치, 좌표계)
    │   ├── layout.py         # 입력값 → 칸 좌표 계산, 입력 범위, QR 내용
    │   └── render_pdf.py     # 좌표 → PDF
    ├── pipeline/
    │   ├── align.py          # P1 사진 → 마커 검출 → 방향 판별 → 정렬 → QR → 칸 잘라내기
    │   ├── flow.py           # P1~P5 연결 (사진 한 장 상태: read / align_failed / wrong_exam / too_bright / too_blurry)
    │   └── read.py           # P3 규칙 기반 판독: 잉크 농도 방식(기본) / 채움 비율 방식 → 문항별 답·학번
    ├── grading/
    │   ├── answer_key.py     # 정답표·배점 (JSON / 엑셀 입력, 빈 정답표 양식 만들기)
    │   ├── score.py          # 판독 결과 + 정답표 → 점수 (확정 / 검수 대기 구분)
    │   └── excel.py          # 채점 결과 엑셀 (학생별 점수표, 문항별 결과·정답률, 검수 대기)
    ├── tools/
    │   ├── make_sheet.py     # 웹 없이 명령행으로 답안지 만들기
    │   ├── grade_photos.py   # 웹 없이 명령행으로 채점: 정답표 + 사진 폴더 → 엑셀
    │   ├── run_pipeline.py   # 사진 폴더를 P1~P5 그대로 돌려 보기
    │   ├── demo_end_to_end.py # 가상 학생 답안지로 전체 흐름 시연 + 판독 정확도 확인
    │   ├── smoke_test.py     # 가상 촬영 사진으로 정렬·좌표 검증
    │   ├── synth_eval.py     # 합성 데이터셋(라벨 포함)으로 판독 정확도 평가 (--method darkness|fill)
    │   ├── synth_augment.py  # 합성 사진에 흐림·부분 반사를 넣은 가공 데이터셋 만들기 (재촬영 기준 실험용)
    │   ├── check_team_form.py # 우리 양식 좌표가 팀 JSON과 같은지 확인
    │   └── team_form/        # 팀 좌표 JSON 사본
    ├── fonts/NotoSansKR-subset.ttf   # 한글 글꼴 (SIL OFL)
    ├── storage/              # 생성 결과·계정·설정 (자동 생성, git 제외. 아래 '저장 방식')
    └── requirements.txt
```

## 실행

- 처음이면 `../checkmate 문서/설명서/VS_CODE_실행가이드.docx`부터 (설치 → 데모 → 웹 화면 순서로 정리)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

브라우저에서 **http://localhost:8000** 을 열면 로그인 화면이 나옴.
- **처음 실행**(계정 0개)이면 '첫 관리자 계정 만들기' 화면이 나옴 → 만든 관리자로 '관리자' 탭 로그인 → `#/admin/users`에서 선생님(사용자) 계정을 만듦
- 선생님은 '사용자' 탭으로 로그인 → 새 시험 만들기 → 값을 고르고 "답안지 PDF 만들기" → 미리보기·내려받기

API 문서는 http://localhost:8000/docs 에서 볼 수 있음. `/api/auth/status·setup·login·logout` 외의 API는 모두 로그인이 필요함 (쿠키 `cm_session`, 또는 명령행·테스트용 `Authorization: Bearer <토큰>` 헤더).

## 웹 → 백엔드로 전달하는 값

`POST /api/answer-sheets`

```json
{
  "num_questions": 45,          // 필수, 정수 5~45
  "num_choices": 5,             // 필수, 정수 2~5
  "orientation": "portrait",    // "portrait"(세로, 기본) | "landscape"(가로)
  "exam_name": "2026학년도 2학기 중간고사",   // 선택, 30자 이하, QR에만 저장
  "subject": "컴퓨터비전"                     // 선택, 20자 이하, QR에만 저장
}
```

범위 검사는 세 곳에서 함: 프론트엔드(입력 제한), FastAPI(pydantic `Field(ge, le)` → 범위 밖이면 422), `SheetSpec.validate()`.
범위 숫자는 `layout.py`의 `NUM_QUESTIONS_RANGE`, `NUM_CHOICES_RANGE` 한 곳에만 있고, 프론트엔드는 `GET /api/sheet-options`로 받아 씀.

응답 (201):
```json
{
  "exam_id": "EX-20261001-8C7353",
  "template_id": "P45Q5C", "template_version": "1",
  "pdf_url": "/api/answer-sheets/EX-20261001-8C7353/pdf",
  "template_url": "/api/templates/P45Q5C/1",
  ...
}
```

| API | 설명 |
|---|---|
| `GET /api/sheet-options` | 입력 가능 범위 |
| `POST /api/answer-sheets` | 답안지 생성 |
| `GET /api/answer-sheets/{exam_id}` | 시험 기록 |
| `GET /api/answer-sheets/{exam_id}/pdf` | PDF (`?download=true`면 내려받기) |
| `GET /api/templates/{template_id}/{version}` | 양식 좌표 JSON |

웹 담당이 React로 화면을 새로 만들 때는 위 API를 그대로 호출하면 됨. CORS는 `localhost:5173`, `localhost:3000`을 허용해 둠.

## 채점 흐름 (2-3 규칙 기반 판독, 2-4 채점·엑셀)

- 합성 데이터셋(라벨 포함)으로 정확도 평가: `python tools/synth_eval.py --data <synthetic_dataset 폴더> --out <결과 폴더>`
- 모듈끼리 어떻게 이어지는지(A의 출력 → B의 입력)는 `../checkmate 문서/설명서/PIPELINE.docx` 참고. 연결 코드는 `backend/pipeline/flow.py`

```
정답표 입력 → 답안지 사진 올리기 → 정렬·QR 확인 → 규칙 기반 판독 → (애매하면 검수) → 채점 → 엑셀
```

### 명령행으로 (backend 폴더에서)

```bash
# 1) 답안지 만들기 → 출력된 시험 ID 확인
python tools/make_sheet.py --num-questions 20 --num-choices 5 --exam-name "중간고사"
# 2) 빈 정답표 엑셀 만들기 → 열어서 '정답'(예: 3, 복수 정답은 1,4)과 '배점' 채우기
python tools/grade_photos.py --exam-id EX-... --make-key-template
# 3) 정답표 + 사진 폴더 → 채점 결과 엑셀
python tools/grade_photos.py --exam-id EX-... --key 정답표.xlsx --photos ./photos --out 결과.xlsx
```

인쇄·촬영 없이 한 번에 시험해 보려면: `python tools/demo_end_to_end.py --students 15`
(가상 학생 15명의 답안지 사진을 만들어 판독·채점하고 `demo_out/results.xlsx`를 만듦.)

### 웹 API로

| API | 설명 |
|---|---|
| `GET /api/exams/{exam_id}/answer-key/template` | 빈 정답표 엑셀 내려받기 |
| `PUT /api/exams/{exam_id}/answer-key` | 정답표 입력 (JSON: `{"answers": {"1": 3, "2": [1,4]}, "points": {"5": 2}}`) |
| `POST /api/exams/{exam_id}/answer-key/upload` | 정답표 파일 올리기 (.xlsx / .json) |
| `POST /api/exams/{exam_id}/sheets` | 답안지 사진 여러 장 올리기 → 정렬·판독 |
| `GET /api/exams/{exam_id}/sheets` / `.../sheets/{sheet_id}` | 판독 결과 목록 / 한 장 전체 |
| `GET /api/exams/{exam_id}/answer-key` | 저장된 정답표 |
| `GET /api/exams/{exam_id}/answer-key/draft` | 지금까지 입력된 정답 (문항 범위별 입력 중이면 빈 문항 `missing` 포함) |
| `PATCH /api/exams/{exam_id}/answer-key/draft` | 내가 맡은 문항의 정답·배점만 저장. 모든 문항이 차면 정답표 완성(`complete=True`) |
| `GET /api/exams` | 내가 볼 수 있는 시험 목록 |
| `DELETE /api/exams/{exam_id}` | 시험 삭제 (시험 관리자) |
| `GET /api/exams/{exam_id}/sheets/{sheet_id}/image` | 정렬 이미지 (검수 화면 사진) |
| `PATCH /api/exams/{exam_id}/sheets/{sheet_id}/review` | 검수 수정 (`{"corrections": {"7": 2}, "student_id": "2026..."}`) |
| `GET /api/exams/{exam_id}/results` / `results.xlsx` | 채점 결과 JSON / 엑셀 (문항 범위가 있으면 범위별 소계 포함) |

로그인·계정·권한 API는 아래 '로그인·계정·권한' 참고.

http://localhost:8000/docs 에서 파일을 직접 올려 시험해 볼 수 있음.

### P3 규칙 기반 판독 (`pipeline/read.py`)

판독 방식은 `ReadConfig.method`로 고름. 기본은 `"darkness"`(잉크 농도, 2026-11-06~), 이전 방식 `"fill"`(채움 비율)은 비교 실험용으로 남겨 둠.

**잉크 농도 방식 (`method="darkness"`, 기본)** — 종이 대비 평균 잉크 농도
1. **인쇄 마스크**: 같은 선지 번호(학번은 같은 값) 칸들의 중앙값 이미지에서 진한 곳 = 칸 안 인쇄 숫자·테두리 → 판정에서 뺌 (사진마다 스스로 맞춤)
2. 칸마다 픽셀 잉크 농도 = (종이 밝기 − 픽셀) / 종이 밝기 (0~1)를 구해 3가지 값 계산
   - `g`: 안쪽 70% 원의 평균 잉크 농도 (정상 마킹 0.76~1.0 / 흐림·지운 흔적 0.15~0.40 / 빈칸 0.00~0.09)
   - `cov`: 안쪽 원에서 진한 픽셀(0.45 초과) 비율 → 얇게 채움·체크 구분
   - `ring`: 칸 바깥 링(반지름 1.12~1.45배)의 진한 픽셀 비율 → 동그라미 표시 확인
3. 칸 상태: marked(`g` 또는 `cov` ≥ 0.60) / ambiguous(`cov` ≥ 0.25) / light(`g` ≥ 0.10) / ring(안은 비고 바깥 링에 잉크) / blank
4. 문항 판정
   - ambiguous 칸 있음 → 보류 (검수)
   - marked 칸 있음 → 답 = marked 칸. 같은 문항의 light 칸은 **지운 흔적**으로 보고 무시
   - marked 없이 ring 칸 → 보류 (동그라미 표시, CNN 전까지 사람 확인)
   - marked 없이 light 칸 1개 → 흐린 마킹. `faint_policy="accept"`(기본)면 답, `"review"`면 보류
   - 아무것도 없음 → 무응답 (단 조금 밝은 사진이면 보류)

**과노출(너무 밝은 사진) 처리** — 칸 주변 인쇄 잉크 대비(사진 전체 중앙값) 기준
| 인쇄 대비 | 처리 |
|---|---|
| 0.24 미만 (`expo_retake`) | 아주 밝음 → `flow.py` 상태 `too_bright` = **재촬영 필요** (판독 결과는 참고용으로 남김) |
| 0.24 ~ 0.42 (`expo_min`) | 조금 밝음 → 채점은 하되 **무응답 문항만 검수** (흐린 마킹이 날아갔을 수 있음) |
| 0.42 이상 | 정상 |

- 부분 반사: 문항 주변 인쇄 대비가 `glare_min`(0.38)보다 낮으면 그 문항 검수, 반사 문항이 30%를 넘으면 장 전체 재촬영
- 흐린 사진: 선명도(`blur_var`)가 `blur_min`(100) 미만이면 판독하지 않고 `too_blurry` = 재촬영 필요
- `expo_policy="review"`면 재촬영 없이 0.42 미만은 모두 무응답 문항만 검수

**채움 비율 방식 (`method="fill"`, 이전 방식)**
1. 정렬 이미지를 **적응형 이진화** (영역별 밝기 기준으로 흑백 구분)
2. 동그라미 **안쪽 70% 원**에서 검은 픽셀 비율(fill) 계산 → fill ≥ 0.60 마킹 / 0.25 ~ 0.60 **애매** / 0.25 미만 빈칸

**두 방식 공통**
- 판독 전 칸 위치 미세 보정 (`refine_offsets`, 아래 '정렬 순서' 7번)
- 문항별 답 형식 (3주차 회의): `[3]` 정상, `[2, 5]` 복수 응답, `[]` 무응답, `null` **판정 보류** (→ 검수)
- 학번도 자리마다 같은 방식. 한 자리라도 정상이 아니면 학번 검수

기준값은 모두 **합성 데이터로 정한 임시값**임 (잉크 농도 기준: 합성 1,004장·22.6만 칸, 과노출 기준: 합성 10,044장, 목표 재촬영률 5% 이하).
실제 촬영 사진이 생기면 다시 정해야 함. 관리자 화면 `#/admin/settings`에서 일부 값(재촬영 기준, 밝은 사진 기준, 마킹 인정 농도, 흐린 자국 농도, 동그라미 기준, 흐린 마킹 처리 등)을 바꿀 수 있고 다음에 올리는 사진부터 적용됨.

판독 실험 도구 (backend 폴더에서)
```bash
# 합성 데이터셋 평가. --method fill 로 이전 방식과 비교
python tools/synth_eval.py --data <synthetic_dataset 폴더> --out <결과 폴더> --method darkness
# 흐림·부분 반사 가공 데이터셋 만들기 (원본은 읽기만 함) → 가공 폴더를 --data, 원본을 --ref로 평가
python tools/synth_augment.py --src <원본 synthetic_dataset> --out <가공 폴더> [--per 80] [--kinds blur,glare]
python tools/synth_eval.py --data <가공 폴더> --ref <원본 synthetic_dataset> --out <결과 폴더>
```

### 채점 규칙 (`grading/score.py`)

| 판독 결과 | 채점 |
|---|---|
| 응답 1개, 정답 목록에 있음 | 정답 (배점) |
| 응답 1개, 정답 아님 | 오답 0점 |
| 복수 응답 | 0점 (검수 대기 시트에 '확인 권장'으로 표시) |
| 무응답 | 0점 |
| 판정 보류 | **검수 대기** (점수에 넣지 않음) |

검수 대기 문항이 있거나 학번이 불완전하면 답안지 상태가 **검수 대기**가 되고, 엑셀에서 확정 점수와 따로 표시됨
('현재 확정분'과 '최고 가능 점수'). 검수에서 답을 고치면(`review`) 그 답으로 다시 채점되어 **확정**이 됨.
정렬에 실패한 사진은 **재촬영 필요**로 남고, QR이 다른 시험인 사진은 이 시험 결과에 저장하지 않음.

### 채점 결과 엑셀 시트

1. **학생별 점수표**: 학번, 상태(확정/검수 대기/재촬영 필요), 확정 점수, 최고 가능 점수, 정답·오답 수, 평균·최고·최저
2. **문항별 결과**: 학생 × 문항 표. 읽은 답을 쓰고 색으로 정답/오답/복수/무응답/검수 대기 구분
3. **문항별 정답률**: 정답률(확정 응답 기준)과 선지별 선택 수 (오답 분포)
4. **검수 대기**: 확인할 문항·학번과 칸별 채움 비율
5. **정답표**: 채점에 쓴 정답·배점

주관식 5문항은 5단계(OCR·채점)에서 연결할 예정이라 아직 점수에 들어가지 않음.

### 가상 데이터 판독 결과 (`demo_end_to_end.py`, 학생 15명 × 20문항, 이전 채움 비율 방식 기준)

| 마킹 유형 | 문항 | 정확 | 검수로 보냄 | 오판독 |
|---|---|---|---|---|
| 진하게 칠함 | 235 | 235 | 0 | 0 |
| 무응답 | 14 | 14 | 0 | 0 |
| 두 칸 칠함 | 13 | 13 | 0 | 0 |
| 반만 옅게 칠함 | 28 | 0 | 28 | 0 |
| 지우고 다시 칠함 | 10 | 10 | 0 | 0 |

'오판독'(틀린 답을 자동 확정)은 0건. 다만 가짜 마킹이라 이 수치는 **코드가 의도대로 동작한다는 확인**이지 실제 성능이 아님.

## 로그인·계정·권한

### 계정 역할 (`app/accounts.py`)

| 역할 | 할 수 있는 것 | 로그인 탭 |
|---|---|---|
| `admin` 관리자 | 관리자 화면만 씀 (지난 시험 관리·계정·양식·시스템 설정). 모든 시험을 열어 볼 수 있음 | 관리자 |
| `user` 사용자 | 시험을 만들 수 있음(→ 그 시험의 시험 관리자). 다른 시험에는 참가자로 들어감 | 사용자 |

- 처음 실행(계정 0개)이면 로그인 화면이 '첫 관리자 계정 만들기'를 보여 줌. 계정이 하나라도 있으면 이 기능은 막힘
- 탭과 역할이 안 맞으면 로그인 거절 (관리자 계정은 '관리자' 탭, 사용자 계정은 '사용자' 탭)
- 비밀번호는 PBKDF2-SHA256 해시(솔트 포함)만 저장, 최소 8자. 아이디는 영문 소문자·숫자·`_ . -` 3~30자
- 로그인 토큰은 `storage/secret.key`로 서명해 HttpOnly 쿠키 `cm_session`으로 줌. 기본 12시간, '로그인 상태 유지'면 30일
- 비밀번호 변경·초기화·계정 사용 중지 때 예전 토큰은 모두 무효가 됨

### 시험별 역할 (`app/access.py`)

같은 사용자가 A 시험에서는 시험 관리자, B 시험에서는 참가자일 수 있음.

| 시험별 역할 | 권한 |
|---|---|
| 소유자(owner, 시험을 만든 사람) / `manager` 공동 시험 관리자 | 검수 + 정답표 입력·수정 + 참여자·문항 범위 관리 + 시험 삭제 |
| `review` 참가자 · 검수 가능 | 보기 + 사진 올리기 + 검수 수정 |
| `view` 참가자 · 보기만 | 시험 정보·PDF·정답표·판독 결과·채점 결과·엑셀 보기 |
| 관리자(admin 계정) | 모든 시험에서 소유자 권한 + 담당(소유자) 바꾸기 |

- 참여자 추가·권한 변경은 소유자·관리자만, 담당(owner) 바꾸기는 관리자만
- `access.json`이 없는 예전 시험은 소유자 없음 → 관리자만 보임. `#/admin/exams`에서 담당을 정해 주면 됨

### 문항 범위 담당 (통합 시험)

여러 선생님이 문항을 나눠 내는 시험용. 예: `{"name": "물리", "from": 1, "to": 10, "assignees": ["teacher02"]}`
- 담당자는 **자기 범위 문항만** 정답 입력·검수함. 소유자·관리자는 모든 문항
- 범위를 맡지 않은 '검수 가능' 참가자(예: 조교)는 모든 문항 검수
- 정답은 범위별로 따로 저장되다가(`answer_key_draft.json`, `PATCH .../answer-key/draft`) 모든 문항이 차면 정답표가 완성됨
- 결과·엑셀에 범위(과목)별 소계가 붙음

### 웹 화면 (주소 → 페이지)

| 주소 | 페이지 | 누가 |
|---|---|---|
| `#/exams` | 시험 목록 (처음 화면) | 사용자 |
| `#/new` · `#/overview` · `#/key` · `#/upload` · `#/review` · `#/results` | 새 시험 → 시험 현황 → 정답 입력 → 사진 올리기 → 검수 → 결과·엑셀 | 사용자 (시험별 권한에 따라 버튼을 숨기거나 막음, 서버도 같은 검사) |
| `#/admin/exams` | 지난 시험 관리: 모든 시험의 담당·날짜·답안지 수·상태(준비 / 검수 중 / 완료), 담당 바꾸기, 엑셀로 내보내기 | 관리자 |
| `#/admin/users` | 계정 관리: 만들기·이름/역할 바꾸기·사용 중지·비밀번호 초기화(임시 비밀번호) | 관리자 |
| `#/admin/templates` | 답안지 양식 목록 + 양식마다 쓰는 시험 수 | 관리자 |
| `#/admin/settings` | 시스템 설정: 판독 기준값 | 관리자 |
| `#/account` | 내 계정 (비밀번호 바꾸기) | 모두 |

### 검수 화면 (`#/review`)

- **왼쪽 사진, 오른쪽 문항 확인** 좌우 배치. 사진은 화면을 내려도 따라옴
- 사진은 기본으로 판독 부분(객관식·서술형 칸)만 크게 보여 줌. '전체 사진' 버튼으로 전환. 학번은 오른쪽 학번 입력칸 밑에 그 칸 사진만 따로 보여 줌
- 기계가 확인 필요로 표시한 문항은 사진에서 주황 테두리, 오른쪽 문항 카드도 테두리로 표시
- 오른쪽 문항에 마우스를 올리거나 누르면 왼쪽 사진에서 그 줄을 파랗게 짚고 보이게 스크롤
- '모든 문항 보기'로 확인 필요 문항 외 전체를 볼 수 있음. 맡지 않은 범위 문항은 보기만 함
- 답안지 목록은 화면 아래. 필터: 검수 필요 / 전체 / 재촬영

### 로그인·계정·권한 API

| API | 설명 |
|---|---|
| `GET /api/auth/status` | 로그인 전 화면용. `needs_setup=True`면 첫 관리자 만들기 |
| `POST /api/auth/setup` | 첫 관리자 계정 만들기 + 바로 로그인 (계정이 이미 있으면 409) |
| `POST /api/auth/login` | 로그인 (`as_admin`으로 탭 구분, `remember`로 유지). 쿠키 `cm_session` |
| `POST /api/auth/logout` | 로그아웃 |
| `GET /api/auth/me` | 지금 로그인한 계정 (안 했으면 401) |
| `POST /api/auth/password` | 내 비밀번호 바꾸기 (`old_password`, `new_password`) |
| `GET /api/users/directory` | 참여자 추가용 사용 중인 계정 목록 (아이디·이름·역할) |
| `GET /api/exams/{exam_id}/access` | 시험의 소유자·참여자·문항 범위·내 권한(`my_level`)·내 범위(`my_scope`) |
| `PUT /api/exams/{exam_id}/access` | 참여자·문항 범위 저장 (`{"members": {"teacher02": "review"}, "sections": [...]}`). `owner` 변경은 관리자만 |
| `GET /api/admin/exams` / `exams.xlsx` | 전체 시험 현황 / 목록 엑셀 |
| `GET /api/admin/templates` | 답안지 양식 목록 |
| `GET /api/admin/settings` / `PUT /api/admin/settings` | 판독 기준값 보기(지금 값·기본값·범위) / 저장 (예: `{"expo_retake": 0.2}`) |
| `GET /api/admin/users` / `POST /api/admin/users` | 계정 목록(+소유 시험 수) / 계정 만들기 (비밀번호를 비우면 임시 비밀번호를 한 번만 보여 줌) |
| `PATCH /api/admin/users/{username}` | 이름·역할·사용 여부 바꾸기 |
| `POST /api/admin/users/{username}/reset-password` | 비밀번호 초기화 → 임시 비밀번호 |

## 저장 방식

```
storage/templates/P45Q5C_v2.layout.json        ← 양식(칸 배치). 같은 배치는 여러 시험이 공유
storage/exams/EX-20261001-8C7353/exam.json     ← 시험 정보 + 사용한 양식
storage/exams/EX-20261001-8C7353/answer_sheet.pdf
storage/exams/EX-20261001-8C7353/answer_key.json      ← 정답표·배점
storage/exams/EX-20261001-8C7353/answer_key_draft.json ← 문항 범위별로 입력 중인 정답 (다 차기 전)
storage/exams/EX-20261001-8C7353/access.json          ← 시험별 소유자·참여자·문항 범위
storage/exams/EX-20261001-8C7353/sheets/S-XXXXXXXX.json ← 답안지 한 장 판독 결과 (+ 검수 수정)
storage/exams/EX-20261001-8C7353/sheets/S-XXXXXXXX_aligned.jpg ← 정렬 이미지 (검수 화면용)
storage/exams/EX-20261001-8C7353/results.xlsx         ← 채점 결과 엑셀
storage/users.json      ← 계정 (비밀번호는 해시만)
storage/secret.key      ← 로그인 토큰 서명 키 (처음 실행 때 자동 생성. 지우면 모든 로그인이 끊김)
storage/settings.json   ← 관리자 화면 시스템 설정(판독 기준값). 없거나 빠진 항목은 ReadConfig 기본값
storage/admin_exam_list.xlsx ← 관리자 '엑셀로 내보내기' 결과 (덮어씀)
```

- **`users.json`, `secret.key`는 절대 커밋하면 안 됨.** `storage/`는 `.gitignore`로 제외되어 있음 (`git check-ignore`로 확인함, `*.key`도 따로 제외)

- 칸 위치·크기는 **팀 양식**(pptx `PDF 생성기 양식`, 좌표 JSON `json양식`)을 그대로 따름 (`TEMPLATE_VERSION` 2). 45문항·5지선다면 마커·객관식 동그라미·서술형 칸이 팀 JSON과 같고, `python tools/check_team_form.py`로 확인함. 팀 JSON 사본은 `backend/tools/team_form/`.
- **template_id**는 입력값에서 바로 만듦: `P45Q5C` = 세로(P)·45문항·5지선다. 가로는 `L`.
- **template_version**은 `layout.py`의 `TEMPLATE_VERSION`. 칸 배치 코드를 바꾸면 올려야 함.
  저장된 양식과 같은 id·version인데 좌표가 다르면(`geometry_hash` 불일치) 생성을 멈추고 알려 줌. 옛 인쇄본에 새 좌표가 잘못 쓰이는 일을 막기 위함.
- 좌표는 **mm, 용지 왼쪽 위 원점**. 정렬 이미지 기준 px는 200dpi(세로 1654×2339, 가로 2339×1654)이고, `bbox_to_px()`로 변환함.

양식 JSON 주요 항목: `frame`(마커·QR 위치), `name_box`, `student_id.bubbles[]`(digit_index, value),
`mcq.questions[].choices[]`(q, choice, center_mm, radius_mm, bbox_mm), `short_answers.items[]`(no, answer_bbox_mm = OCR 영역).

## QR 코드 내용

```
CM1|<exam_id>|<template_id>|<template_version>|<과목명>|<시험명>
예) CM1|EX-20261001-8C7353|P45Q5C|2|컴퓨터비전|2026학년도 2학기 중간고사
```
그래서 시험명·과목명에는 `|`를 쓸 수 없음.

## 정렬 순서 (`pipeline/align.py`)

1. ArUco 검출 (ID 0~3, 서브픽셀 코너 보정). 마커 세트 2가지를 다 찾음 (`frame.MARKER_SETS`)
   - `team`: 팀 좌표 JSON·합성 데이터셋·우리 PDF 생성기 (`DICT_6X6_50`, TL0 TR1 BL2 BR3, 18.249mm)
   - `print`: 실제 인쇄해서 쓴 답안지 (`OMR_A4_가로형_수정본_인쇄.pptx`, `DICT_4X4_50`, TL0 TR1 BR2 BL3, 16mm). 세로 인쇄본 값은 실측 사진이 없어 미확인
2. **방향·마커 세트 판별**: 세트·방향 조합마다 변환을 구해 보고 마커 모양이 가장 잘 맞는 쪽을 고름
3. 코너 12~16점으로 호모그래피 계산 (RANSAC). 마커 3개만 보여도 정렬, 2개 이하면 재촬영 안내
4. 정면 이미지로 펴기 (200dpi)
5. 정렬된 이미지의 QR 고정 위치에서 QR 읽기 → template_id·version으로 양식 JSON 불러오기
6. 양식 좌표로 객관식·학번 버블, 주관식 답 칸 잘라내기
7. 판독 전 칸 위치 미세 보정 (`read.refine_offsets`): 객관식 열·학번 칸마다 인쇄된 동그라미 테두리를 찾아 ±2.5mm 안에서 맞춤. 인쇄본은 객관식 칸이 팀 JSON보다 약 1.7mm 왼쪽이라 필요함

## 가상 촬영 테스트 결과 (실제 사진 아님)

```bash
cd backend
python tools/smoke_test.py --orientation portrait --num-questions 45 --num-choices 5 --trials 10
python tools/smoke_test.py --orientation landscape --num-questions 45 --num-choices 5 --trials 10
```

팀 양식 반영 후(2026-10-14, 난이도 easy·medium·hard 각 10장):

| 양식 | 정렬 성공 | 방향·QR 인식 | 칸 중심 오차 평균 / 최대 | 객관식 판독 |
|---|---|---|---|---|
| P45Q5C (세로) | 30/30 | 30/30 | 0.08~0.10 / 0.45 mm | 100% |
| L45Q5C (가로) | 30/30 | 30/30 | 0.08~0.13 / 0.37 mm | 100% |

팀 양식은 마커가 용지 끝에서 4mm 안쪽이라, 사진을 종이에 꽉 차게 찍으면 마커가 화면 밖으로 잘리기 쉬움(데모의 hard 사진 12장 중 1장). 마커 4개가 다 보이게 여백을 두고 찍어야 함.
가상 사진에는 종이 휨·구김·렌즈 왜곡이 없으므로, 실제 인쇄·촬영 검증은 예산이 들어온 뒤 필요함.

## VS Code에서 빨간 줄이 뜰 때

- `checkmate` 폴더를 VS Code로 열면 `pyrightconfig.json`이 `backend`를 import 경로에 넣어 줌 (`from sheetgen ...` 인식).
- 실행은 `backend` 폴더에서 함 (`cd backend`). 다른 폴더에서 실행하면 `ModuleNotFoundError: sheetgen`이 남.
