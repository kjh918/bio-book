import os
import time
from dash import html, dcc, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify

from app.pages.base import LimsDashApp

# ========================================================
# ⚠️ 연구원님의 실제 LLM 스크립트 함수들을 import 하세요!
from app.core.llm_engine import load_json_documents, simple_retrieve, build_context, load_model, generate_response, SYSTEM_PROMPT

# ========================================================
# ⚙️ LLM 고정 파라미터 설정
# ========================================================

LLM_CONFIG = {
    "model_path": "/storage/home/jhkim/models/qwen2.5-3b-instruct-q8_0.gguf",
    "json_path": "/storage/home/jhkim/Projects/cbNIPT/260427-GCX-cbNIPT-LLM/Workplace/build_rag/evidence.jsonl",
    "top_k": 5,
    "max_new_tokens": 1024,
    "temperature": 0.3,
    "top_p": 0.9
}
# ========================================================
# 🧠 글로벌 메모리 공간 (서버 구동 시 1회만 로드)
# ========================================================
GLOBAL_TOKENIZER = None
GLOBAL_MODEL = None
CURRENT_MODEL_PATH = None

def init_llm(model_path):
    global GLOBAL_TOKENIZER, GLOBAL_MODEL, CURRENT_MODEL_PATH
    if GLOBAL_MODEL is None or CURRENT_MODEL_PATH != model_path:
        print(f"🔄 메모리에 GGUF 모델 로드 시작: {model_path}")
        GLOBAL_TOKENIZER, GLOBAL_MODEL = load_model(model_path)
        CURRENT_MODEL_PATH = model_path
        print("✅ GGUF 모델 로드 완료!")

# ========================================================
# 웰컴 레이아웃 분리 (숨김/표시 전환용)
# ========================================================
def get_welcome_layout():
    return html.Div([
        DashIconify(icon="carbon:bot", width=40, className="text-primary mb-3"),
        html.H5("안녕하세요! AI 연구 어시스턴트입니다.", className="fw-bold"),
        html.P("분석 범위가 넓어 막막하시다면, 아래 추천 질문 중 하나를 선택해 보세요.", className="text-muted mb-4"),
        
        # 추천 질문 버튼 그룹
        html.Div([
            dbc.Button("🧬 특정 유전자(예: FGFR3) 병원성 확인", id="btn-suggest-1", n_clicks=0, 
                       color="light", className="m-2 rounded-pill border shadow-sm text-secondary"),
            dbc.Button("📚 ACMG 가이드라인 분류 기준 요약", id="btn-suggest-2", n_clicks=0, 
                       color="light", className="m-2 rounded-pill border shadow-sm text-secondary"),
            dbc.Button("🔬 21번 염색체 삼염색체증 임상적 영향", id="btn-suggest-3", n_clicks=0, 
                       color="light", className="m-2 rounded-pill border shadow-sm text-secondary")
        ], className="d-flex justify-content-center flex-wrap")
        
    ], className="text-center mt-5 pt-5", id="welcome-message-container", style={"display": "block"})

# ========================================================
# 1. 화면 레이아웃
# ========================================================
def create_chatbot_layout():
    return html.Div([
        dbc.Row([
            # 🗂️ 좌측 사이드바
            dbc.Col([
                html.Div([
                    dbc.Button([DashIconify(icon="carbon:add", className="me-2"), "새 대화 시작"], 
                               id="btn-new-chat", color="light", outline=True, className="w-100 fw-bold mb-4 text-start rounded-3"),
                    
                    html.H6("이전 대화 기록", className="text-muted mb-3 small fw-bold px-2"),
                    html.Div(id="chat-sessions-list", children=[
                        html.Div([DashIconify(icon="carbon:chat", className="me-2"), "현재 대화 세션"], 
                                 className="p-2 mb-2 rounded", style={"backgroundColor": "#343541", "color": "white", "cursor": "pointer"})
                    ], style={"overflowY": "auto", "height": "calc(100vh - 200px)"})
                ], style={"height": "85vh", "backgroundColor": "#202123", "color": "white", "padding": "20px", "borderRadius": "15px 0 0 15px"})
            ], xs=12, lg=2, className="pe-0"),
            
            # 💬 우측 메인 채팅 화면
            dbc.Col([
                html.Div([
                    html.Div([
                        html.H4([DashIconify(icon="carbon:machine-learning-model", className="me-2 text-primary"), "RAG 기반 연구 어시스턴트"], 
                                className="fw-bold mb-0 text-center"),
                    ], className="p-3 border-bottom shadow-sm bg-white", style={"borderRadius": "0 15px 0 0"}),
                    
                    # [MODIFIED] 대화 영역 분리: 웰컴 레이아웃과 말풍선 전용 컨테이너
                    html.Div(
                        id="chat-scroll-area",
                        children=[
                            get_welcome_layout(),
                            html.Div(id="chat-bubbles-container") # 채팅 말풍선은 이곳에만 쌓임
                        ],
                        style={"flexGrow": 1, "overflowY": "auto", "padding": "40px", "backgroundColor": "#f8f9fa"}
                    ),
                    
                    # 입력 창
                    html.Div([
                        html.Div([
                            dbc.InputGroup([
                                dbc.Input(id="chat-user-input", placeholder="메시지를 직접 입력하거나 위 버튼을 클릭하세요...", n_submit=0, 
                                          style={"borderRadius": "25px 0 0 25px", "paddingLeft": "20px", "border": "1px solid #ced4da"}),
                                dbc.Button(DashIconify(icon="carbon:send-alt", width=20), id="btn-chat-send", color="primary", 
                                           style={"borderRadius": "0 25px 25px 0", "padding": "0 20px"})
                            ], className="shadow-sm")
                        ], style={"maxWidth": "800px", "margin": "0 auto"}),
                        html.Div("AI가 생성한 답변은 부정확할 수 있으므로 연구 자료와 함께 교차 검증하시기 바랍니다.", 
                                 className="text-center text-muted small mt-2")
                    ], style={"padding": "20px", "backgroundColor": "white", "borderTop": "1px solid #e9ecef", "borderRadius": "0 0 15px 0"})
                    
                ], style={"display": "flex", "flexDirection": "column", "height": "85vh", "backgroundColor": "#ffffff", "borderRadius": "0 15px 15px 0", "boxShadow": "-5px 0 15px rgba(0,0,0,0.05)"})
            ], xs=12, lg=10, className="ps-0")
        ], className="m-0 shadow-sm rounded-4"),
        
        dcc.Store(id="chat-history-store", data=[]),
        dcc.Loading(id="loading-chat", type="dot", children=html.Div(id="dummy-chat-loading"))
        
    ], className="pb-5", style={"padding": "30px", "backgroundColor": "#eef2f5", "minHeight": "100vh"})


# ========================================================
# 2. 콜백 로직
# ========================================================
def register_chatbot_callbacks(dash_app):
    
    # 🆕 새 대화 시작 버튼 (초기화)
    @dash_app.callback(
        [Output("chat-history-store", "data", allow_duplicate=True),
         Output("chat-bubbles-container", "children", allow_duplicate=True),
         Output("welcome-message-container", "style", allow_duplicate=True)],
        Input("btn-new-chat", "n_clicks"),
        prevent_initial_call=True
    )
    def start_new_chat(n_clicks):
        # 대화 기록 지우고, 말풍선 지우고, 웰컴 화면 다시 표시
        return [], [], {"display": "block"}

    # 💬 채팅 메시지 처리
    @dash_app.callback(
        [Output("chat-history-store", "data"),
         Output("chat-bubbles-container", "children"),
         Output("welcome-message-container", "style"), # [MODIFIED] 웰컴 화면 숨김 제어
         Output("chat-user-input", "value"),
         Output("dummy-chat-loading", "children")],
        [Input("btn-chat-send", "n_clicks"),
         Input("chat-user-input", "n_submit"),
         Input("btn-suggest-1", "n_clicks"), 
         Input("btn-suggest-2", "n_clicks"), 
         Input("btn-suggest-3", "n_clicks")],
        [State("chat-user-input", "value"),
         State("chat-history-store", "data")],
        prevent_initial_call=True
    )
    def process_chat(n_send, n_submit, n_s1, n_s2, n_s3, user_input, chat_history):
        
        trigger_id = ctx.triggered_id

        # 트리거에 따른 실제 질의어 할당
        if trigger_id == "btn-suggest-1":
            user_text = "FGFR3 유전자의 돌연변이 병원성 및 관련 유전 질환에 대해 요약해 줘."
        elif trigger_id == "btn-suggest-2":
            user_text = "ACMG/AMP 가이드라인에서 변이의 병원성을 분류하는 주요 기준들을 설명해 줘."
        elif trigger_id == "btn-suggest-3":
            user_text = "21번 염색체 삼염색체증(다운증후군)의 태아기 임상적 영향과 주요 소견은 무엇인가요?"
        else:
            if not user_input or not user_input.strip():
                return no_update, no_update, no_update, no_update, no_update
            user_text = user_input.strip()
            
        chat_history.append({"role": "user", "content": user_text})
        
        try:
            cfg = LLM_CONFIG
            docs = load_json_documents(cfg["json_path"])
            retrieved = simple_retrieve(query=user_text, docs=docs, top_k=cfg["top_k"])
            context = build_context(retrieved)
            
            init_llm(cfg["model_path"])
            
            ai_response = generate_response(
                tokenizer=GLOBAL_TOKENIZER,
                model=GLOBAL_MODEL,
                user_prompt=user_text,
                context=context,
                system_prompt=SYSTEM_PROMPT,
                max_new_tokens=cfg["max_new_tokens"],
                temperature=cfg["temperature"],
                top_p=cfg["top_p"]
            )
        except Exception as e:
            ai_response = f"⚠️ RAG 파이프라인 에러 발생: {str(e)}"

        chat_history.append({"role": "assistant", "content": ai_response})
        
        ui_bubbles = []
        for msg in chat_history:
            if msg["role"] == "user":
                bubble = html.Div(
                    html.Div(msg["content"], style={"backgroundColor": "#f0f4f9", "color": "#202124", "padding": "15px 20px", "borderRadius": "25px", "display": "inline-block", "maxWidth": "80%", "textAlign": "left"}),
                    className="text-end mb-4"
                )
            else:
                bubble = html.Div([
                    DashIconify(icon="carbon:bot", width=28, className="text-primary me-2", style={"float": "left", "marginTop": "5px"}),
                    html.Div(msg["content"], style={"color": "#202124", "padding": "5px 15px", "display": "inline-block", "maxWidth": "85%", "whiteSpace": "pre-wrap", "textAlign": "left", "lineHeight": "1.6"})
                ], className="text-start mb-4", style={"overflow": "hidden"})
            ui_bubbles.append(bubble)

        # [MODIFIED] 웰컴 화면은 이제 삭제되지 않고 '숨김(display: none)' 처리됩니다.
        # 따라서 버튼 객체들이 DOM에 남아있어 다음 질문 시 콜백 먹통이 발생하지 않습니다.
        return chat_history, ui_bubbles, {"display": "none"}, "", ""


def create_chatbot_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_chatbot_layout)
    app = lims.get_app() 
    register_chatbot_callbacks(app)
    return app