BASE_MAPPING = {
    # 엑셀 헤더명 : DB 컬럼명
    "Patient ID/ Sample ID": "sample_name",
    "Tumor Type": "cancer_type",
    "Specimen Type": "specimen",
    "Sample Group": "sample_group",          # 🚀 Base로 승격!
    "Pairing Info.": "pairing_info",         # 🚀 Base로 승격!
    "Sample Label (of tube)": "outside_id_1",
    "Remarks": "issue_comment",
    "특이사항": "sample_issue", 
    "Extraction 필요 유무": "extraction_required",
    # "번호": 엑셀 단순 순번이므로 매핑 제외 (시스템이 ID를 자동 발급)
}

# ==========================================
# 🚀 2. 패널별 특수 매핑 (Special Mapping) - JSON 보따리로 들어갈 항목들
# ==========================================
SPECIAL_MAPPING = {
    "TSO500": {
        "Nucleic Acid Type": {"db_col": "nucleic_acid_type", "is_extra": True},
        "Clinical Report": {"db_col": "req_clinical_report", "is_extra": True},
        "Advanced Analysis Report": {"db_col": "req_advanced_report", "is_extra": True}
    },
    "WGS": {
        "WGS Output Data": {"db_col": "wgs_output_data", "is_extra": True},
        "Standard Analysis Report": {"db_col": "req_standard_report", "is_extra": True},
        "Advanced Analysis Report": {"db_col": "req_advanced_report", "is_extra": True}
    },
    "WES": {
        "WES Output Data": {"db_col": "wes_output_data", "is_extra": True},
        "Standard Analysis Report": {"db_col": "req_standard_report", "is_extra": True},
        "Advanced Analysis Report": {"db_col": "req_advanced_report", "is_extra": True}
    },
    "WTS": {
        "WTS Output Data": {"db_col": "wts_output_data", "is_extra": True},
        "Standard Analysis Report": {"db_col": "req_standard_report", "is_extra": True},
        "Advanced Analysis Report": {"db_col": "req_advanced_report", "is_extra": True}
    },
    "dPCR": {
        "EGFR": {"db_col": "egfr", "is_extra": True},
        "Etc.": {"db_col": "other_marker", "is_extra": True},
    },
}

def get_full_mapping_for_panel(panel_type):
    # 기본 맵 복사
    full_map = {k: {"db_col": v, "is_extra": False} for k, v in BASE_MAPPING.items()}
    
    # 패널별 특수 맵 병합
    if panel_type in SPECIAL_MAPPING:
        full_map.update(SPECIAL_MAPPING[panel_type])
        
    return full_map

FACILITY_MAPPING = {
    #"C00": {"facility": "Unknown", "team": ""},
    "C01": {"facility": "GCX", "team": "NGS"},
    "C02": {"facility": "GMC", "team": "NGS"},
    "C03": {"facility": "GCX", "team": "연구소"},
    "C04": {"facility": "GCX", "team": "학술"},
    "C11": {"facility": "오가노이드사이언스", "team": "Deputy General Manager"},
    "C12": {"facility": "칠곡경북대학교병원", "team": "혈액종양내과"},
    "C13": {"facility": "셀레믹스", "team": "Sales & Marketing Dept."},
    "C14": {"facility": "마크로젠", "team": "Clinical Sales Dept."},
    "C15": {"facility": "포도테라퓨틱스", "team": "(CTO)"},
    "C16": {"facility": "테라젠", "team": "NGS Consulting Team"},
    "C17": {"facility": "오가노이드사이언스", "team": "사업개발 (세브란스의뢰)"},
    "C18": {"facility": "제노스케이프", "team": "(CEO)"},
    "C20": {"facility": "지니너스", "team": "오믹스사업팀"},
    "C21": {"facility": "국립암센터", "team": "병리과"},
    "C22": {"facility": "랩지노믹스", "team": "마케팅"},
    "C23": {"facility": "한림대산학협력단", "team": "신호승교수"},
    "C24": {"facility": "삼성서울병원", "team": "유방외과"}
}

