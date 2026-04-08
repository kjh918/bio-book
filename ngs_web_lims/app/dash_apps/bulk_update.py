import os
import pandas as pd
from dash import html, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from sqlalchemy import create_engine
from app.core.database import SessionLocal
from app.models.schema import Sample

# [ADD] 새롭게 만든 Base Class 임포트
from app.dash_apps.base import LimsDashApp
from app.dash_apps.utils import create_alert, get_safe_db_session


def create_dash_app(requests_pathname_prefix: str):
    if not requests_pathname_prefix:
        raise ValueError("requests_pathname_prefix 경로가 필수입니다.")

    # [MODIFIED] Dash() 직접 호출 대신 Base Class 인스턴스 생성
    lims_app = LimsDashApp(__name__, requests_pathname_prefix)
    app = lims_app.get_app()

    def load_data():
        db_url = os.getenv("LIMS_DATABASE_URL")
        if not db_url: raise ValueError("LIMS_DATABASE_URL 누락")
        engine = create_engine(db_url)
        return pd.read_sql("SELECT sample_id, project_id, status, metrics FROM samples", engine)

    # [MODIFIED] Navbar나 배경색 설정 없이 '내부 컨텐츠'만 정의
    def inner_content():
        return html.Div([
            dbc.Row([
                # [ADD] 반응형 그리드 속성(xs, md) 추가로 창 크기가 줄어도 깨지지 않음
                dbc.Col(html.H2("🧬 NGS LIMS: Sample Status", className="text-primary mb-3"), xs=12, md=10),
                dbc.Col(dbc.Button("새로고침 🔄", id='refresh-button', color="secondary", outline=True, className="w-100"), xs=12, md=2)
            ], className="mb-3"),
            
            dbc.Card([
                dbc.CardBody([
                    html.Div(id='table-container')
                ])
            ], className="shadow-sm mb-4 border-0"),
            
            dbc.Row([
                dbc.Col(dbc.Button("💾 DB에 일괄 저장", id='save-button', color="success", size="lg", className="shadow-sm w-100"), xs=12, md=3),
                dbc.Col(html.Div(id='save-result-msg', className="mt-2 fs-5"), xs=12, md=9)
            ])
        ])

    # [MODIFIED] Base Class에 내부 컨텐츠 세팅
    lims_app.set_content(inner_content)

    @app.callback(
        Output('table-container', 'children'),
        Input('refresh-button', 'n_clicks')
    )
    def update_table(n_clicks):
        try:
            df = load_data()
            if df.empty: 
                return dbc.Alert("데이터베이스에 등록된 샘플이 없습니다.", color="warning")
            
            if 'metrics' in df.columns:
                metrics_df = pd.json_normalize(df['metrics'])
                df = pd.concat([df.drop('metrics', axis=1), metrics_df], axis=1)

            # 컬럼 규칙 정의 (Status만 드롭다운)
            columns = [
                {"name": c.upper(), "id": c, "editable": False} if c != "status" 
                else {"name": c.upper(), "id": c, "presentation": "dropdown", "editable": True} 
                for c in df.columns
            ]

            # [MODIFIED] 수십 줄의 style 코드를 지우고 공통 테이블 생성기 호출
            return LimsDashApp.create_standard_table(
                id='editable-table',
                columns=columns,
                data=df.to_dict('records'),
                editable=True,
                dropdown={
                    'status': {
                        'options': [{'label': i, 'value': i} for i in ['RECEIVED', 'EXPERIMENTING', 'COMPLETED', 'FAILED']]
                    }
                }
            )
        except Exception as e:
            return dbc.Alert(f"데이터 로드 에러: {e}", color="danger")

    @app.callback(
        Output('save-result-msg', 'children'),
        Input('save-button', 'n_clicks'),
        State('editable-table', 'data')
    )
    def save_to_db(n_clicks, table_data):
        if not n_clicks or not table_data: raise PreventUpdate

        # 기존의 지저분한 try-except-finally 코드가 사라짐
        try:
            updated_count = 0
            with get_safe_db_session() as db:  # 공통 함수 사용
                for row in table_data:
                    sample_obj = db.query(Sample).filter(Sample.sample_id == row['sample_id']).first()
                    if sample_obj and sample_obj.status != row['status']:
                        sample_obj.status = row['status']
                        updated_count += 1
                        
            # 공통 Alert 함수 사용
            if updated_count > 0:
                return create_alert(True, "상태 저장 완료", updated_count)
            return dbc.Alert("변경사항이 없습니다.", color="info", duration=3000)

        except Exception as e:
            return create_alert(False, str(e))
    
    return app