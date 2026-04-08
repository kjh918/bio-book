import os
import json
import yaml
import datetime
from dash import html, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from app.models.schema import NGSTracking

# [ADD] 새롭게 만든 Base Class 및 유틸리티 임포트
from app.dash_apps.base import LimsDashApp
from app.dash_apps.utils import create_alert, get_safe_db_session

# 1. YAML 설정 로더
def load_column_config():
    config_path = f"{os.path.dirname(__file__)}/config/columns.yaml"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)['tracking_columns']

def create_excel_tracker_app(requests_pathname_prefix: str):
    if not requests_pathname_prefix: raise ValueError("경로 접두사 필수")

    # 2. Base Class 초기화
    lims_app = LimsDashApp(__name__, requests_pathname_prefix)
    app = lims_app.get_app()

    # 3. DB 데이터 로드 로직
    def load_db_data():
        with get_safe_db_session() as db:
            results = db.query(NGSTracking).all()
            if not results: return []
                
            records = []
            for row in results:
                raw_data = row.excel_data
                record = json.loads(raw_data) if isinstance(raw_data, str) else dict(raw_data)
                record['Order ID/GCXID'] = row.order_id
                record['Sample Name'] = row.sample_name
                record['SEQ ID'] = row.seq_id
                records.append(record)
            return records

    # 4. 내부 컨텐츠 정의 (UI)
    def inner_content():
        column_rules = load_column_config()
        
        # YAML 기반 컬럼 및 드롭다운 동적 생성
        dt_columns = [
            {
                "name": col, 
                "id": col, 
                "presentation": "dropdown" if "options" in rule else "input",
                "type": rule.get("type", "text")
            } for col, rule in column_rules.items()
        ]
        dt_dropdown = {
            col: {'options': [{'label': i, 'value': i} for i in rule['options']]}
            for col, rule in column_rules.items() if "options" in rule
        }

        return html.Div([
            dbc.Row([
                dbc.Col(html.H2("📊 Master Tracking Sheet", className="text-primary mb-3"), xs=12, md=8),
                dbc.Col(dbc.Button("➕ 5행 추가", id='add-rows-btn', color="info", className="w-100 mb-2"), xs=6, md=2),
                dbc.Col(dbc.Button("💾 일괄 저장", id='save-db-btn', color="success", className="w-100 mb-2"), xs=6, md=2)
            ]),
            
            dbc.Card([
                dbc.CardBody([
                    # [MODIFIED] 수십 줄의 스타일 설정을 공통 함수로 대체
                    LimsDashApp.create_standard_table(
                        id='excel-table',
                        columns=dt_columns,
                        data=load_db_data(),
                        editable=True,
                        row_deletable=True,
                        filter_action="native",
                        sort_action="native",
                        dropdown=dt_dropdown,
                        column_selectable="single",
                        cell_selectable=True
                    )
                ])
            ], className="shadow-sm mt-3 mb-3 border-0"),
            html.Div(id='action-msg', className="fs-5 mt-2")
        ])

    # 5. Base Class에 레이아웃 세팅
    lims_app.set_content(inner_content)

    # --- 콜백 로직 ---

    @app.callback(
        Output('excel-table', 'data', allow_duplicate=True),
        Input('add-rows-btn', 'n_clicks'),
        State('excel-table', 'data'),
        prevent_initial_call=True
    )
    def add_empty_rows(n_clicks, current_data):
        if n_clicks is None: raise PreventUpdate
        current_data = current_data or []
        cols = list(load_column_config().keys())
        current_data.extend([{col: "" for col in cols} for _ in range(5)])
        return current_data

    @app.callback(
        Output('action-msg', 'children'),
        Output('excel-table', 'data'),
        Input('save-db-btn', 'n_clicks'),
        State('excel-table', 'data'),
        prevent_initial_call=True
    )
    def save_to_db(n_clicks, table_data):
        if n_clicks is None: raise PreventUpdate
        
        try:
            # [MODIFIED] get_safe_db_session 유틸리티 사용으로 try-except-finally 구조 단순화
            with get_safe_db_session() as db:
                
                # [1. 백업 로직] 삭제 전 현재 상태 JSON 백업
                backup_dir = "backups/tracking"
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(backup_dir, f"tracking_backup_{timestamp}.json")
                
                current_db_records = db.query(NGSTracking).all()
                if current_db_records:
                    backup_content = [{"seq_id": r.seq_id, "excel_data": r.excel_data} for r in current_db_records]
                    with open(backup_file, "w", encoding="utf-8") as f:
                        json.dump(backup_content, f, ensure_ascii=False, indent=4)

                # [2. 동기화(삭제) 로직] 화면에 없는 SEQ ID 삭제
                current_seq_ids = [row.get('SEQ ID') for row in table_data if row.get('SEQ ID')]
                deleted_items = db.query(NGSTracking).filter(~NGSTracking.seq_id.in_(current_seq_ids)).all()
                deleted_count = len(deleted_items)
                db.query(NGSTracking).filter(~NGSTracking.seq_id.in_(current_seq_ids)).delete(synchronize_session=False)

                # [3. Upsert 로직]
                saved_count = 0
                for row in table_data:
                    order_id = row.get('Order ID/GCXID')
                    if not order_id or str(order_id).strip() == "": continue

                    sample_name = row.get('Sample Name')
                    seq_id = row.get('SEQ ID')

                    if not sample_name or not seq_id:
                        raise ValueError(f"'{order_id}'의 Sample Name/SEQ ID 누락")

                    existing = db.query(NGSTracking).filter(NGSTracking.seq_id == seq_id).first()
                    if existing:
                        existing.order_id = str(order_id)
                        existing.sample_name = str(sample_name)
                        existing.excel_data = row
                    else:
                        db.add(NGSTracking(
                            order_id=str(order_id), sample_name=str(sample_name),
                            seq_id=str(seq_id), excel_data=row
                        ))
                    saved_count += 1
            
            # with 블록을 성공적으로 빠져나오면 자동 커밋됨
            msg = f"동기화 완료! ({saved_count}건 저장, {deleted_count}건 삭제)"
            return create_alert(True, msg), load_db_data()

        except Exception as e:
            # 예외 발생 시 자동 롤백됨
            return create_alert(False, str(e)), table_data

    return app