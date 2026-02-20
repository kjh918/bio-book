from pathlib import Path
from jinja2 import Environment

class Page:
    def __init__(self, filename: str, template: str, context: dict):
        self.filename = filename
        self.template = template
        self.context = context

class BookPageBuilder:
    def __init__(self, env: Environment, output_dir: Path, meta_config: dict, template_prefix: str = "manual"):
        self.env = env
        self.output_dir = output_dir.resolve() # 안전한 절대경로 출력 보장
        self.meta_config = meta_config
        self.template_prefix = template_prefix 
        self.toc = []
        self.pages = []
        self._current_part = None

    def start_part(self, title: str):
        self._current_part = {"part": title, "chapters": []}
        self.toc.append(self._current_part)

    def end_part(self):
        self._current_part = None

    def add_chapter(self, filename: str, template: str, context: dict = None):
        ctx = self.meta_config.copy()
        if context: ctx.update(context)
        self.pages.append(Page(filename, template, ctx))
        
        if self._current_part is not None:
            self._current_part["chapters"].append(filename)
        else:
            self.toc.append(filename)

    def build(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for page in self.pages:
            template_path = f"{self.template_prefix}/{page.template}" if self.template_prefix else page.template
            tmpl = self.env.get_template(template_path)
            
            with open(self.output_dir / page.filename, "w", encoding='utf-8') as f:
                f.write(tmpl.render(page.context))
        
        q_tmpl = self.env.get_template(f"{self.template_prefix}/_quarto.yml.j2" if self.template_prefix else "_quarto.yml.j2")
        yml_context = self.meta_config.copy()
        yml_context["toc"] = self.toc 
        
        with open(self.output_dir / "_quarto.yml", "w", encoding='utf-8') as f:
            f.write(q_tmpl.render(yml_context))