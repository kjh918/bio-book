# gencurix_report

`Gencurix_PPT_Template.pptx` 템플릿을 분석 결과 데이터로 자동으로 채워서
보고용 `.pptx`를 생성하는 Python 패키지입니다.

- 입력: 순수 Python 객체(dataclass) — `ReportData` 하나
- 출력: 완성된 `.pptx` 파일
- 이미지(PNG 차트 등), 표(Table), 텍스트(bullet/문단) 를 콘텐츠 영역에 자동 삽입
- 템플릿에 존재하는 색상/폰트/레이아웃 스타일은 그대로 유지 (텍스트만 in-place 치환)

## 설치

```bash
pip install python-pptx Pillow
```

패키지 폴더(`gencurix_report/`)를 프로젝트에 복사해서 쓰거나, `pip install -e .`
로 로컬 설치하면 됩니다 (setup.py 미포함 시 `sys.path`에 상위 폴더만 추가해도 동작).

## 빠른 시작

```python
from gencurix_report import (
    ReportBuilder, ReportData, TitlePageData, ChapterItem, SummaryData,
    DividerData, SampleInfoData, ResultItem, ConclusionData, ContentBlock, TableData,
)

data = ReportData(
    title_page=TitlePageData(
        title="cbNIPT Analysis Report",
        subtitle="Chromosome 13 Trisomy Detection, Sample NIPT-2026-0143",
        writer="지훈", team="Clinical Bioinformatics Team", date="2026-07-08",
    ),
    chapters=[
        ChapterItem(name="Introduction & Workflow"),
        ChapterItem(name="Sample Information"),
        ChapterItem(name="Results"),
        ChapterItem(name="Conclusion"),
    ],
    summary=SummaryData(
        purpose=["cfDNA 기반 태아 염색체 이수성 비침습 검출"],
        results=["Chr13 Z-score = 3.8 (양성)"],
        conclusion=["Trisomy 13 소견, 확진검사 권고"],
        further_study=["양수천자 등 확진검사 권고"],
    ),
    divider_intro=DividerData(number="01", name="Introduction"),
    workflow_content=ContentBlock(bullets=["cfDNA 추출", "라이브러리 준비 및 시퀀싱", "정렬 및 GC 보정", "Z-score 산출"]),
    sample_info=SampleInfoData(content=ContentBlock(table=TableData(
        headers=["Sample ID", "GA", "Fetal Fraction", "Total Reads"],
        rows=[["NIPT-2026-0143", "12w3d", "11.2%", "6,842,110"]],
    ))),
    divider_results=DividerData(number="02", name="Results"),
    results=[
        ResultItem(title="Chr13 Z-score Overview", content=ContentBlock(image_path="chart.png")),
        ResultItem(title="Aneuploidy Call Summary", content=ContentBlock(table=TableData(
            headers=["Chromosome", "Z-score", "Call"],
            rows=[["13", "3.8", "Positive"], ["18", "0.1", "Normal"]],
        ))),
    ],
    divider_conclusion=DividerData(number="03", name="Conclusion"),
    conclusion=ConclusionData(
        title="Chromosome 13 Trisomy Detected",
        content_1=ContentBlock(bullets=["Z-score 3.8, 임상 임계값(+3.0) 초과"]),
        content_2=ContentBlock(bullets=["확진검사 및 유전상담 권고"]),
    ),
)

ReportBuilder().build(data, "output.pptx")
```

전체 동작 예시는 `examples/example_generate.py` 참고 (matplotlib 차트 생성 → 삽입까지 포함).

## 슬라이드 구성 및 순서 (고정)

패키지가 만드는 최종 덱은 항상 아래 순서입니다 (요청하신 순서와 동일):

| # | 슬라이드 | 데이터 소스 | 비고 |
|---|----------|------------|------|
| 1 | Color Guide (컬러 가이드) | 없음 | 템플릿 그대로 고정, 편집 안 함 |
| 2 | Main / Title page | `title_page` | |
| 3 | Contents (목차) | `chapters` (최대 4개) | |
| 4 | Summary | `summary` | 4분면: Purpose/Results/Conclusion/Further Study |
| 5 | Chapter Divider | `divider_intro` | "01 Introduction" 같은 챕터 구분 슬라이드 |
| 6 | Introduction | 없음 (섹션 제목만) | |
| 7 | Workflow (제목) | 없음 (섹션 제목만) | |
| 7-1 | Workflow (내용, 선택) | `workflow_content` | 내용을 주면 Sample Info 레이아웃을 복제해서 자동 추가 |
| 8 | Sample / Data Information | `sample_info` | 안 주면 슬라이드 자체가 삭제됨 |
| 9 | Chapter Divider | `divider_results` | 안 주면 삭제 |
| 10..N | Results (반복) | `results` (list) | 항목이 여러 개면 템플릿 슬라이드를 자동 복제 |
| N+1 | Chapter Divider | `divider_conclusion` | 안 주면 삭제 |
| N+2 | Conclusion | `conclusion` | 안 주면 삭제 |
| 마지막 | End slide | 없음 | 템플릿 그대로 고정 |

## 입력 객체 / 인식 변수 전체 목록

패키지가 인식하는 모든 데이터 객체와, 그 값이 실제로 채워지는 템플릿상의 placeholder
(원본 템플릿에 있던 텍스트) 매핑입니다.

| 데이터 객체 | 필드 | 원본 템플릿 placeholder | 타입 |
|---|---|---|---|
| `TitlePageData` | `title` | `[Title]` | str |
| | `subtitle` | `[subtitle]` | str |
| | `writer`, `team`, `date` | `[writer] ｜[team] ｜[date]` | str |
| `ChapterItem` (최대 4개, `chapters=[...]`) | `name` | TOC의 `제목을 입력해 주십시오` (CHAPTER 1~4 슬롯) | str |
| `SummaryData` | `purpose` | Purpose 분면 `내용을 입력해 주십시오...` | list[str] |
| | `results` | Results 분면 | list[str] |
| | `conclusion` | Conclusion 분면 | list[str] |
| | `further_study` | Further Study 분면 | list[str] |
| `DividerData` (`divider_intro` / `divider_results` / `divider_conclusion`) | `number` | `[Number]` | str (예: `"01"`) |
| | `name` | `[Chapter Name]` | str |
| `ContentBlock` (`workflow_content`) | `bullets` / `paragraphs` / `table` / `image_path` | Workflow 슬라이드의 `[CONTENTS]` | 아래 참고 |
| `SampleInfoData.content` | 〃 | Sample Information 슬라이드의 `[CONTENTS]` | 〃 |
| `ResultItem` (`results=[...]`, 반복 가능) | `title` | `Results : [TITLE]` 및 `[TITLE]` 라벨 박스 | str |
| | `content` | `[CONTENTS]` | `ContentBlock` |
| `ConclusionData` | `title` | `[TITLE]` | str |
| | `content_1` | 위쪽 `[CONTENTS]` | `ContentBlock` |
| | `content_2` | 아래쪽 `[CONTENTS]` | `ContentBlock` |

### `ContentBlock` (공용 "내용 채우기" 객체)

`[CONTENTS]` 라고 쓰인 자리는 전부 이 객체 하나로 처리됩니다. 필드 중 **하나만**
채우세요 (우선순위: `image_path` > `table` > `bullets` > `paragraphs`):

```python
ContentBlock(bullets=["항목1", "항목2"])                 # 불릿 리스트
ContentBlock(paragraphs=["문단1", "문단2"])               # 불릿 없는 문단
ContentBlock(table=TableData(headers=[...], rows=[[...]]))  # 표
ContentBlock(image_path="chart.png")                     # PNG/JPG 이미지 (예: matplotlib로 저장한 차트)
```

- `image_path`: 원래 placeholder의 위치/크기 박스에 맞춰 **비율을 유지하며** 자동 축소/중앙정렬되어 삽입됩니다.
- `table`: PowerPoint 네이티브 표로 삽입됩니다 (템플릿 테이블 스타일 적용).
- `bullets`/`paragraphs`: 템플릿의 기존 글머리 기호·폰트·크기 서식을 그대로 복제해서 줄 수만큼 문단을 생성합니다.

## 알아두면 좋은 동작

- **TOC(목차)** 는 최대 4개 챕터까지 지원합니다. 4개보다 적게 주면 남는 분면은
  슬라이드에서 완전히 제거됩니다 (빈 칸으로 남지 않음).
- **Results 슬라이드**는 `results` 리스트 길이만큼 자동으로 슬라이드를 복제합니다
  (1개면 템플릿 슬라이드 1장, 3개면 3장).
- **Divider(챕터 구분) 슬라이드**는 템플릿에 정확히 3장이 이미 존재하며, 각각
  `divider_intro` / `divider_results` / `divider_conclusion` 에 대응됩니다.
  해당 값을 `None`으로 주면 그 구분 슬라이드는 최종 결과물에서 삭제됩니다.
- **Workflow 내용 슬라이드**는 선택 사항입니다. `workflow_content`를 주면
  Sample Information과 같은 레이아웃을 복제해 "Workflow" 제목으로 자동 삽입됩니다.
  안 주면 "Workflow" 섹션 제목 슬라이드만 남습니다 (원본 템플릿 그대로).
- **Color Guide(1페이지)** 와 **마지막 클로징 슬라이드**는 항상 템플릿 그대로
  유지되며 편집 대상이 아닙니다.

## 패키지 구조

```
gencurix_report/
├── __init__.py          # 공개 API (ReportBuilder, 모든 데이터 클래스)
├── models.py            # 입력 데이터 클래스 정의 (여기 있는 것만 채우면 됨)
├── slide_utils.py        # 저수준 pptx 조작: 슬라이드 복제/이동/삭제, 텍스트/표/이미지 채우기
├── fill_content.py       # ContentBlock -> 실제 슬라이드 반영 dispatcher
├── builder.py            # ReportBuilder: 전체 조립 로직
└── assets/
    └── Gencurix_PPT_Template.pptx   # 기본 내장 템플릿 (원하면 다른 템플릿 경로 지정 가능)

examples/
└── example_generate.py   # matplotlib 차트 생성 + 표 + bullet 전체 사용 예시
```

`ReportBuilder(template_path="다른_템플릿.pptx")` 로 템플릿을 바꿔 낄 수도 있지만,
그 경우 이 문서의 slide 인덱스/placeholder 매핑이 그대로 맞아야 합니다
(즉, `Gencurix_PPT_Template.pptx`와 동일한 슬라이드 구조를 따르는 템플릿이어야 합니다).

## YAML로 입력하기

Python 코드 없이 YAML 파일 하나로 전체 리포트를 정의할 수 있습니다.

```python
from gencurix_report import build_from_yaml
build_from_yaml("report_config.yaml", "output.pptx")
```

또는 커맨드라인에서:

```bash
python -m gencurix_report.yaml_loader report_config.yaml output.pptx
```

전체 예시는 `examples/report_config.yaml` (+ `examples/data/`의 샘플 PNG/TSV) 참고.
아래는 스키마 요약입니다.

```yaml
main:
  title: 제목
  subtitle: 부제목
  writer: 작성자        # 선택
  team: 팀명            # 선택
  date: 2026-07-08      # 선택, 생략 시 오늘 날짜 자동 사용

slides:
  contents:                     # 이 리스트의 순서 = 목차 순서 = 슬라이드 순서
                                 # (최대 4개 섹션; 키 이름으로 섹션 종류를 자동 인식:
                                 #  "Summary"/"Introduction"/"Results"/"Conclusion"로
                                 #  시작하는 이름이면 인식됨 -- "Introduction & Workflow"도 OK)

    - Summary:
        purpose: ["...", "..."]        # 문자열 하나 또는 리스트 모두 가능
        results: ["..."]
        conclusion: ["..."]
        further_study: ["..."]

    - Introduction:
        workflow:
          workflow_png:                # PNG 이미지로 채우기
            path: data/workflow.png
            position: [0.5, 1.5]       # [left, top] 인치 단위, 생략 가능
            size: [9.0, 3.0]           # [width, height] 인치 단위, 생략 가능
          # 또는 workflow_table: {path: ..., position:.., size:..}  (TSV/CSV)
          # 또는 bullets: ["...", "..."]  (텍스트만)
        Sample Information:
          sample_info_table:           # TSV/CSV 파일 경로로 표 채우기
            path: data/sample_info_table.tsv
            position: [0.5, 1.5]
            size: [9.0, 1.0]
          # 또는 sample_info_png: {path:.., position:.., size:..}

    - Results:
        items:                          # 개수만큼 슬라이드 자동 복제
          - title: "결과 제목 1"
            image:
              path: data/result1.png
              position: [0.7, 1.6]
              size: [8.5, 3.8]
          - title: "결과 제목 2"
            table:
              path: data/result2.tsv
              position: [0.7, 1.8]
              size: [8.5, 2.5]

    - Conclusion:
        title: "결론 제목"
        Conclusion:
          text: ["...", "..."]          # 문자열 또는 리스트
        Further study:
          text: ["..."]
```

**position / size 규칙**
- 둘 다 인치(inch) 단위, `[값1, 값2]` 형식입니다.
- `position` = `[left, top]`, `size` = `[width, height]`.
- 둘 다 생략하면 템플릿에 원래 있던 placeholder 박스 위치/크기를 그대로 사용합니다.
- 이미지(`image`/`workflow_png`/`sample_info_png`)는 지정된 박스 안에 **비율을 유지**하며
  자동 축소/중앙정렬됩니다. 표(`table`)는 박스 크기에 정확히 맞춰 삽입됩니다.
- 파일 확장자로 구분자를 자동 인식합니다: `.tsv`/`.txt` → 탭 구분, 그 외(`.csv` 등) → 콤마 구분.
  첫 번째 줄은 항상 헤더로 처리됩니다.

**섹션 종류 자동 인식**: `contents`의 각 키 이름을 소문자로 바꿔서
`summary` / `introduction` (또는 `intro`) / `results` (또는 `result`) / `conclusion`
로 시작하는지 확인합니다. 즉 `"Introduction & Workflow"`, `"Results Overview"`
같은 이름도 그대로 목차에 표시되면서 올바른 섹션 핸들러에 연결됩니다.
매칭되지 않는 이름은 목차에는 나오지만 내용 슬라이드는 생성되지 않습니다.

## 확장하기

- **여러 개의 Sample Info 슬라이드**가 필요하면 `ResultItem`과 동일한 패턴으로
  `_fill_sample_info`를 리스트 반복 방식으로 바꾸면 됩니다 (현재는 1장 고정).
- **표에 폰트/색상 커스터마이징**이 필요하면 `slide_utils.fill_table()`을 수정하세요.
- **새로운 콘텐츠 타입**(예: 여러 이미지 그리드)은 `ContentBlock`에 필드를 추가하고
  `fill_content.apply_content_block()`에 분기를 추가하면 됩니다.
