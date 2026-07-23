"""
app/pages/registration/__init__.py
===================================
main.py 에서 호출하는 팩토리 함수.

    from app.pages.registration import create_registration_app
    dash_app = create_registration_app(requests_pathname_prefix="/reg/")
    app.mount("/reg", WSGIMiddleware(dash_app.server))
"""

from .app import create_project_app

__all__ = ["create_project_app"]