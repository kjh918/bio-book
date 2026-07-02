import yaml
from pathlib import Path

# 1. 기준 경로 설정 (프로젝트 최상단)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"

# ==========================================
# [1] 워크플로우 설정 (workflows.yaml)
# ==========================================
WORKFLOW_FILE = CONFIG_DIR / "workflows.yaml"

def load_workflows():
    if not WORKFLOW_FILE.exists():
        raise FileNotFoundError(f"Workflow 설정 파일을 찾을 수 없습니다: {WORKFLOW_FILE}")
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

LIMS_WORKFLOWS = load_workflows()

def get_workflow_for_analysis(analysis_type: str) -> list:
    """분석 종류에 맞는 워크플로우를 반환하며, 없으면 DEFAULT를 반환"""
    clean_type = str(analysis_type).strip().upper() 
    return LIMS_WORKFLOWS.get(clean_type, LIMS_WORKFLOWS.get("DEFAULT"))


# ==========================================
# [2] 컬럼 및 화면 설정 (columns.yaml) - 신규 추가!
# ==========================================
COLUMNS_FILE = CONFIG_DIR / "columns.yaml"
def load_columns():
    if not COLUMNS_FILE.exists():
        raise FileNotFoundError(f"Column 설정 파일을 찾을 수 없습니다: {COLUMNS_FILE}")
    with open(COLUMNS_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# 서버 어디서든 COLUMNS_CONFIG['wet_lab']['columns'] 형태로 꺼내 쓸 수 있습니다.
COLUMNS_CONFIG = load_columns()


# ==========================================
# [2] 컬럼 및 화면 설정 (columns.yaml) - 신규 추가!
# ==========================================
PAGES_FILE = CONFIG_DIR / "pages.yaml"
def load_columns():
    if not PAGES_FILE.exists():
        raise FileNotFoundError(f"Page 설정 파일을 찾을 수 없습니다: {PAGES_FILE}")
    with open(PAGES_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# 서버 어디서든 COLUMNS_CONFIG['wet_lab']['columns'] 형태로 꺼내 쓸 수 있습니다.
PAGES_CONFIG = load_columns()


# ==========================================
# [3] 전역 UI 메뉴 설정 (하드코딩 변수)
# ==========================================
MAIN_MENU_ITEMS = [
    {"name": "Status Dashboard", "path": "/",         "icon": "carbon:dashboard"},
    {"name": "Project View",     "path": "/pro/",     "icon": "carbon:data-table"},
    {"name": "Wet-Lab Board",    "path": "/wetlab/",  "icon": "carbon:chemistry"},
    {"name": "New Registration", "path": "/reg/",     "icon": "carbon:document-add"},
    {"name": "Raw DB Excel",     "path": "/excel/",   "icon": "carbon:database"},
]