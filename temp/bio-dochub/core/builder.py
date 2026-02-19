from pathlib import Path
from jinja2 import Environment

class Page:
    """단일 qmd 페이지를 표현하는 도메인 객체"""
    def __init__(self, filename: str, template: str, context: dict):
        self.filename = filename
        self.template = template
        self.context = context

class BookPageBuilder:
    """Quarto Book의 목차(TOC) 구성 및 페이지 렌더링을 오케스트레이션 하는 빌더"""
    # [MODIFIED] template_prefix 파라미터 추가 (기본값: 'manual')
    def __init__(self, env: Environment, output_dir: Path, meta_config: dict, template_prefix: str = "manual"):
        self.env = env
        self.output_dir = output_dir.resolve() # [MODIFIED] 출력 위치를 절대경로로 확정
        self.meta_config = meta_config
        self.template_prefix = template_prefix
        self.toc = []       # Quarto 목차 구조 (_quarto.yml 용)
        self.pages = []     # 생성할 Page 객체 리스트
        self._current_part = None

    def start_part(self, title: str):
        """Quarto Book의 Part(섹션 묶음) 시작"""
        self._current_part = {"part": title, "chapters": []}
        self.toc.append(self._current_part)

    def end_part(self):
        """Part 묶음 종료"""
        self._current_part = None

    def add_chapter(self, filename: str, template: str, context: dict = None):
        """페이지(Chapter) 객체 생성 및 등록"""
        ctx = self.meta_config.copy()
        if context:
            ctx.update(context)
            
        page = Page(filename, template, ctx)
        self.pages.append(page)
        
        # 목차(TOC) 구조 업데이트
        if self._current_part is not None:
            self._current_part["chapters"].append(filename)
        else:
            self.toc.append(filename)

    def build(self):
        """등록된 모든 Page와 _quarto.yml을 실제 파일로 렌더링"""
        # [MODIFIED] 출력 폴더가 없으면 절대경로 상에 안전하게 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 개별 qmd 페이지 렌더링
        for page in self.pages:
            # [MODIFIED] 파라미터로 받은 prefix를 결합하여 템플릿 경로 유연화
            template_path = f"{self.template_prefix}/{page.template}" if self.template_prefix else page.template
            tmpl = self.env.get_template(template_path)
            
            output_file = self.output_dir / page.filename
            with open(output_file, "w", encoding='utf-8') as f:
                f.write(tmpl.render(page.context))
        
        # 2. _quarto.yml 동적 렌더링
        quarto_template_path = f"{self.template_prefix}/_quarto.yml.j2" if self.template_prefix else "_quarto.yml.j2"
        q_tmpl = self.env.get_template(quarto_template_path)
        
        yml_context = self.meta_config.copy()
        yml_context["toc"] = self.toc 
        
        with open(self.output_dir / "_quarto.yml", "w", encoding='utf-8') as f:
            f.write(q_tmpl.render(yml_context))
            
        print(f"📚 BookPageBuilder: Successfully assembled {len(self.pages)} chapters at {self.output_dir}")