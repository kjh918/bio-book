import os
import time
from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

from app.pages.base import LimsDashApp

# ========================================================
# ⚠️ 연구원님의 실제 LLM 스크립트 함수들을 import 하세요!
# 실제 사용 시 아래 주석(#)을 풀고 mock 함수들을 지워주세요.
from app.core.llm_engine import load_json_documents, simple_retrieve, build_context, load_model, generate_response, SYSTEM_PROMPT


# ========================================================
# 🧠 글로벌 메모리 공간 (서버 구동 시 1회만 로드)
# ========================================================
GLOBAL_TOKENIZER = None
GLOBAL_MODEL = None
CURRENT_MODEL_NAME = None

def init_llm(model_name):
    global GLOBAL_TOKENIZER, GLOBAL_MODEL, CURRENT_MODEL_NAME
    # 현재 로드된 모델과 이름이 다르면 새로 로드합니다.
    if GLOBAL_MODEL is None or CURRENT_MODEL_NAME != model_name:
        GLOBAL_TOKENIZER, GLOBAL_MODEL = load_model(model_name)
        CURRENT_MODEL_NAME = model_name

# ========================================================
# 1. 화면 레이아웃
# ========================================================
def create_chatbot_layout():
    return html.Div([
        html.H3([DashIconify(icon="carbon:chat-bot", className="me-2"), "AI 연구 어시스턴트 (RAG)"], className="fw-bold text-secondary mb-4"),
        
        dbc.Row([
            # 🎛️ 좌측: LLM 파라미터 설정 패널 (argparse 대체)
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("⚙️ 모델 및 검색 설정", className="fw-bold mb-0")),
                    dbc.CardBody([
                        # --model
                        html.Label("모델 (Model)", className="fw-bold text-primary small"),
                        dbc.Input(id="cb-model-input", value="Qwen/Qwen2.5-0.5B-Instruct", className="mb-3"),
                        
                        # --json_path
                        html.Label("증거 자료 경로 (JSON Path)", className="fw-bold text-primary small"),
                        dbc.Input(id="cb-json-path-input", value="/storage/home/jhkim/Projects/cbNIPT/260427-GCX-cbNIPT-LLM/Workplace/build_rag/evidence.jsonl", className="mb-4"),
                        
                        html.Hr(),
                        
                        # --top_k
                        html.Label(id="label-top-k", children="Top K 검색 수: 5", className="fw-bold small"),
                        dcc.Slider(id="cb-top-k-slider", min=1, max=20, step=1, value=5, marks={1: '1', 10: '10', 20: '20'}, className="mb-3"),
                        
                        # --max_new_tokens
                        html.Label(id="label-max-tokens", children="Max New Tokens: 512", className="fw-bold small"),
                        dcc.Slider(id="cb-max-tokens-slider", min=64, max=2048, step=64, value=512, marks={64: '64', 1024: '1K', 2048: '2K'}, className="mb-3"),
                        
                        # --temperature
                        html.Label(id="label-temperature", children="Temperature: 0.3", className="fw-bold small"),
                        dcc.Slider(id="cb-temperature-slider", min=0.0, max=1.0, step=0.1, value=0.3, marks={0: '0', 0.5: '0.5', 1: '1.0'}, className="mb-3"),
                        
                        # --top_p
                        html.Label(id="label-top-p", children="Top P: 0.9", className="fw-bold small"),
                        dcc.Slider(id="cb-top-p-slider", min=0.1, max=1.0, step=0.05, value=0.9, marks={0.1: '0.1', 0.5: '0.5', 1.0: '1.0'}, className="mb-3"),
                        
                    ])
                ], className="border-0 shadow-sm rounded-4 h-100")
            ], xs=12, lg=4, className="mb-4 mb-lg-0"),
            
            # 💬 우측: 채팅 UI 영역
            dbc.Col([
                dbc.Card([
                    # 채팅 내역 출력 창
                    dbc.CardBody(
                        id="chat-history-container",
                        children=[
                            html.Div("AI 어시스턴트입니다. 논문이나 데이터에 대해 무엇이든 물어보세요!", 
                                     className="text-muted text-center mt-3")
                        ],
                        style={"height": "500px", "overflowY": "auto", "backgroundColor": "#f8f9fa", "padding": "20px"}
                    ),
                    # 메시지 입력 창
                    dbc.CardFooter([
                        dbc.InputGroup([
                            dbc.Input(id="chat-user-input", placeholder="질문을 입력하세요...", n_submit=0),
                            dbc.Button([DashIconify(icon="carbon:send-alt", className="me-1"), "전송"], 
                                       id="btn-chat-send", color="primary", className="fw-bold")
                        ])
                    ], style={"backgroundColor": "#ffffff"})
                ], className="border-0 shadow-sm rounded-4 h-100")
            ], xs=12, lg=8)
        ]),
        
        # 채팅 내역 저장을 위한 숨겨진 Store
        dcc.Store(id="chat-history-store", data=[]),
        
        # 로딩 스피너 (AI가 생각하는 동안 표시)
        dcc.Loading(id="loading-chat", type="circle", children=html.Div(id="dummy-chat-loading"), style={"marginTop": "20px"})
        
    ], className="pb-5", style={"padding": "30px", "backgroundColor": "#f4f7f9", "minHeight": "100vh"})


# ========================================================
# 2. 콜백 로직
# ========================================================
def register_chatbot_callbacks(dash_app):
    
    # 슬라이더 값 변경 시 라벨 텍스트 업데이트
    @dash_app.callback(
        Output("label-top-k", "children"), Input("cb-top-k-slider", "value")
    )
    def update_top_k_label(val): return f"Top K 검색 수: {val}"
    
    @dash_app.callback(
        Output("label-max-tokens", "children"), Input("cb-max-tokens-slider", "value")
    )
    def update_max_tokens_label(val): return f"Max New Tokens: {val}"
    
    @dash_app.callback(
        Output("label-temperature", "children"), Input("cb-temperature-slider", "value")
    )
    def update_temp_label(val): return f"Temperature: {val}"

    @dash_app.callback(
        Output("label-top-p", "children"), Input("cb-top-p-slider", "value")
    )
    def update_top_p_label(val): return f"Top P: {val}"

    # 채팅 메시지 처리 및 AI 응답 생성
    @dash_app.callback(
        [Output("chat-history-store", "data"),
         Output("chat-history-container", "children"),
         Output("chat-user-input", "value"),
         Output("dummy-chat-loading", "children")],
        [Input("btn-chat-send", "n_clicks"),
         Input("chat-user-input", "n_submit")],
        [State("chat-user-input", "value"),
         State("chat-history-store", "data"),
         State("cb-model-input", "value"),
         State("cb-json-path-input", "value"),
         State("cb-top-k-slider", "value"),
         State("cb-max-tokens-slider", "value"),
         State("cb-temperature-slider", "value"),
         State("cb-top-p-slider", "value")],
        prevent_initial_call=True
    )
    def process_chat(n_clicks, n_submit, user_input, chat_history, 
                     model_name, json_path, top_k, max_tokens, temp, top_p):
        
        # 입력값이 없으면 무시
        if not user_input or not user_input.strip():
            return no_update, no_update, no_update, no_update
            
        user_text = user_input.strip()
        
        # 1. 사용자 메시지를 기록에 추가
        chat_history.append({"role": "user", "content": user_text})
        
        try:
            # 2. 문서 검색
            docs = load_json_documents(json_path)
            retrieved = simple_retrieve(query=user_text, docs=docs, top_k=top_k)
            context = build_context(retrieved)
            
            # 3. 모델 로드 (이미 글로벌에 올라가 있으면 0초 컷으로 패스됨!)
            init_llm(model_name)
            
            # 4. 답변 생성 (글로벌 메모리에 있는 모델 사용)
            ai_response = generate_response(
                tokenizer=GLOBAL_TOKENIZER,
                model=GLOBAL_MODEL,
                user_prompt=user_text,
                context=context,
                system_prompt=SYSTEM_PROMPT,
                max_new_tokens=max_tokens,
                temperature=temp,
                top_p=top_p
            )
            
        except Exception as e:
            ai_response = f"⚠️ 에러 발생: {str(e)}"

        # 5. AI 메시지를 기록에 추가
        chat_history.append({"role": "assistant", "content": ai_response})
        
        # 6. 화면에 그릴 UI 말풍선(Bubble) 렌더링
        ui_bubbles = []
        for msg in chat_history:
            if msg["role"] == "user":
                bubble = html.Div(
                    html.Div(msg["content"], style={"backgroundColor": "#0d6efd", "color": "white", "padding": "10px 15px", "borderRadius": "15px 15px 0 15px", "display": "inline-block", "maxWidth": "80%", "textAlign": "left"}),
                    className="text-end mb-3"
                )
            else:
                bubble = html.Div([
                    html.Strong("🤖 AI", className="d-block mb-1 text-primary"),
                    html.Div(msg["content"], style={"backgroundColor": "white", "color": "#333", "padding": "10px 15px", "borderRadius": "15px 15px 15px 0", "display": "inline-block", "maxWidth": "80%", "border": "1px solid #ddd", "whiteSpace": "pre-wrap", "textAlign": "left"})
                ], className="text-start mb-3")
            ui_bubbles.append(bubble)

        # 상태 업데이트, UI 갱신, 입력창 초기화
        return chat_history, ui_bubbles, "", ""


def create_chatbot_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_chatbot_layout)
    app = lims.get_app() 
    register_chatbot_callbacks(app)
    return app