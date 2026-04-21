# app/core/rules.py

class LimsRules:
    """LIMS 시스템 전체에서 사용되는 비즈니스 규칙 및 상태값 정의"""

    # 1. 상태 및 단계 (Kanban Stages)
    KANBAN_STAGES = [
        "접수 대기", "접수 완료", "QC 진행", "시퀀싱 진행", "분석 진행", "정산 대기", "완료", "보류/실패"
    ]

    # 2. 단계별 액션 버튼 매핑 룰 (버튼 텍스트, 색상, 다음 단계)
    STAGE_ACTIONS = {
        "접수 대기": {"text": "✅ 접수 심사하기", "color": "outline-dark", "next": "접수 완료"},
        "접수 완료": {"text": "QC 시작 ➡️", "color": "warning", "next": "QC 진행"},
        "QC 진행": {"text": "시퀀싱 시작 ➡️", "color": "primary", "next": "시퀀싱 진행"},
        "시퀀싱 진행": {"text": "분석 시작 ➡️", "color": "success", "next": "분석 진행"},
        "분석 진행": {"text": "정산 단계로 ➡️", "color": "dark", "next": "정산 대기"},
        "정산 대기": {"text": "✅ 최종 완료", "color": "secondary", "next": "완료"}
    }

    # 3. 육안 검수(Visual Inspection) 판정 옵션 룰
    INSPECTION_OPTIONS = [
        {"label": "대기중", "value": ""},
        {"label": "✅ 적합 (모두 일치)", "value": "Pass"},
        {"label": "⚠️ 보류 (용량 부족)", "value": "Hold_Volume"},
        {"label": "⚠️ 보류 (농도 미달)", "value": "Hold_Conc"},      # 언제든 쉽게 옵션 추가 가능!
        {"label": "❌ 불량 (라벨 불일치)", "value": "Fail_Label"},
        {"label": "❌ 불량 (튜브 파손)", "value": "Fail_Broken"}
    ]