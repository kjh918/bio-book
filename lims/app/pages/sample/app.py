from dash import Dash
import dash_bootstrap_components as dbc

from app.ui.shared_ui import apply_modern_layout
from .layout import build_layout
from .callbacks import register_callbacks


def create_sample_app(requests_pathname_prefix: str = "/sample/") -> Dash:
    app = Dash(
        __name__,
        requests_pathname_prefix=requests_pathname_prefix,
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        ],
        suppress_callback_exceptions=True,
    )
    app.layout = lambda: apply_modern_layout(build_layout())
    register_callbacks(app)
    return app