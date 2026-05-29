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
# ⚙️ LLM 고정 파라미터 설정 (웹 UI에서 제거하고 여기서 관리합니다)
# ========================================================
LLM_CONFIG = {
    "model_name": "Qwen/Qwen2.5-0.5B-Instruct",
    "json_path": "/storage/home/jhkim/Projects/cbNIPT/260427-GCX-cbNIPT-LLM/Workplace/build_rag/evidence.jsonl",
    "top_k": 5,
    "max_new_tokens": 512,
    "temperature": 0.3,
    "top_p": 0.9
}


# ========================================================
# 🧠 글로벌 메모리 공간 (서버 구동 시 1회만 로드)
# ========================================================
GLOBAL_TOKENIZER = None
GLOBAL_MODEL = None
CURRENT_MODEL_NAME = None

def init_llm(model_name):
    global GLOBAL_TOKENIZER, GLOBAL_MODEL, CURRENT_MODEL_NAME
    if GLOBAL_MODEL is None or CURRENT_MODEL_NAME != model_name:
        GLOBAL_TOKENIZER, GLOBAL_MODEL = load_model(model_name)
        CURRENT_MODEL_NAME = model_name


# ========================================================
# 1. 화면 레이아웃 (ChatGPT / Gemini 스타일)
# ========================================================
def create_chatbot_layout():
    return html.Div([
        dbc.Row([
            # 🗂️ 좌측 사이드바: 대화 기록 및 새 대화 버튼
            dbc.Col([
                html.Div([
                    dbc.Button([DashIconify(icon="carbon:add", className="me-2"), "새 대화 시작"], 
                               id="btn-new-chat", color="light", outline=True, className="w-100 fw-bold mb-4 text-start rounded-3"),
                    
                    html.H6("이전 대화 기록", className="text-muted mb-3 small fw-bold px-2"),
                    
                    # 채팅 내역 리스트 (현재는 임시 세션 1개만 표시, 추후 DB 연동 시 확장 가능)
                    html.Div(id="chat-sessions-list", children=[
                        html.Div([DashIconify(icon="carbon:chat", className="me-2"), "현재 대화 세션"], 
                                 className="p-2 mb-2 rounded", style={"backgroundColor": "#343541", "color": "white", "cursor": "pointer"})
                    ], style={"overflowY": "auto", "height": "calc(100vh - 200px)"})
                    
                ], style={"height": "85vh", "backgroundColor": "#202123", "color": "white", "padding": "20px", "borderRadius": "15px 0 0 15px"})
            ], xs=12, lg=2, className="pe-0"),
            
            # 💬 우측 메인: 채팅 화면
            dbc.Col([
                html.Div([
                    # 상단 헤더
                    html.Div([
                        html.H4([DashIconify(icon="carbon:machine-learning-model", className="me-2 text-primary"), "RAG 기반 연구 어시스턴트"], 
                                className="fw-bold mb-0 text-center"),
                    ], className="p-3 border-bottom shadow-sm bg-white", style={"borderRadius": "0 15px 0 0"}),
                    
                    # 대화 출력 창
                    html.Div(
                        id="chat-history-container",
                        children=[
                            html.Div([
                                DashIconify(icon="carbon:bot", width=40, className="text-primary mb-3"),
                                html.H5("안녕하세요! AI 연구 어시스턴트입니다.", className="fw-bold"),
                                html.P("논문 데이터나 RAG 지식베이스에 대해 궁금한 점을 물어보세요.", className="text-muted")
                            ], className="text-center mt-5 pt-5")
                        ],
                        style={"flexGrow": 1, "overflowY": "auto", "padding": "40px", "backgroundColor": "#f8f9fa"}
                    ),
                    
                    # 입력 창 (하단 고정)
                    html.Div([
                        html.Div([
                            dbc.InputGroup([
                                dbc.Input(id="chat-user-input", placeholder="메시지를 입력하세요...", n_submit=0, 
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
        
        # 채팅 내역 저장을 위한 숨겨진 Store
        dcc.Store(id="chat-history-store", data=[]),
        dcc.Loading(id="loading-chat", type="dot", children=html.Div(id="dummy-chat-loading"))
        
    ], className="pb-5", style={"padding": "30px", "backgroundColor": "#eef2f5", "minHeight": "100vh"})


# ========================================================
# 2. 콜백 로직
# ========================================================
def register_chatbot_callbacks(dash_app):
    
    # 🆕 새 대화 시작 버튼 (대화 내역 초기화)
    @dash_app.callback(
        [Output("chat-history-store", "data", allow_duplicate=True),
         Output("chat-history-container", "children", allow_duplicate=True)],
        Input("btn-new-chat", "n_clicks"),
        prevent_initial_call=True
    )
    def start_new_chat(n_clicks):
        welcome_msg = html.Div([
            DashIconify(icon="carbon:bot", width=40, className="text-primary mb-3"),
            html.H5("새로운 대화가 시작되었습니다.", className="fw-bold"),
            html.P("무엇을 도와드릴까요?", className="text-muted")
        ], className="text-center mt-5 pt-5")
        
        return [], [welcome_msg]

    # 💬 채팅 메시지 처리 및 AI 응답 생성
    @dash_app.callback(
        [Output("chat-history-store", "data"),
         Output("chat-history-container", "children"),
         Output("chat-user-input", "value"),
         Output("dummy-chat-loading", "children")],
        [Input("btn-chat-send", "n_clicks"),
         Input("chat-user-input", "n_submit")],
        [State("chat-user-input", "value"),
         State("chat-history-store", "data")],
        prevent_initial_call=True
    )
    def process_chat(n_clicks, n_submit, user_input, chat_history):
        
        if not user_input or not user_input.strip():
            return no_update, no_update, no_update, no_update
            
        user_text = user_input.strip()
        
        # 1. 사용자 메시지 추가
        chat_history.append({"role": "user", "content": user_text})
        
        try:
            # 2. 고정된 LLM_CONFIG 설정값 사용
            cfg = LLM_CONFIG
            
            docs = load_json_documents(cfg["json_path"])
            retrieved = simple_retrieve(query=user_text, docs=docs, top_k=cfg["top_k"])
            context = build_context(retrieved)
            
            # 모델 로드 (글로벌 메모리)
            init_llm(cfg["model_name"])
            
            # 3. 답변 생성
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
            ai_response = f"⚠️ 에러 발생: {str(e)}"

        # 4. AI 메시지 추가
        chat_history.append({"role": "assistant", "content": ai_response})
        
        # 5. UI 말풍선 렌더링 (ChatGPT 스타일)
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

        return chat_history, ui_bubbles, "", ""


def create_chatbot_app(requests_pathname_prefix: str):
    lims = LimsDashApp(__name__, requests_pathname_prefix)
    lims.set_content(create_chatbot_layout)
    app = lims.get_app() 
    register_chatbot_callbacks(app)
    return app