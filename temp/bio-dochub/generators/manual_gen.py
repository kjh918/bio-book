from core.base import BaseGenerator
from pathlib import Path
from utils.script_parser import extract_workflow_from_ast

class ManualGenerator(BaseGenerator):
    def prepare_data(self):
        target_src = self.config.get('source_dir', './src')
        self.config['tree_structure'] = self._get_tree_structure(target_src)
        
        pipeline_script = self.config.get('pipeline_script')
        scripts_dir = self.config.get('scripts_dir', './scripts')
        
        if pipeline_script:
            extracted_workflow = extract_workflow_from_ast(pipeline_script, scripts_dir)
            self.config['workflow'] = extracted_workflow

    def _get_tree_structure(self, startpath: str) -> str:
        path = Path(startpath)
        if not path.exists():
            return "Directory not found."
            
        tree_lines = []
        for p in sorted(path.rglob('*')):
            if any(part in ['.git', '__pycache__'] for part in p.parts):
                continue
            depth = len(p.relative_to(path).parts)
            spacer = '  ' * (depth - 1)
            tree_lines.append(f"{spacer}* {p.name}")
        return "\n".join(tree_lines) if tree_lines else "Empty directory."

    def render(self):
        self.prepare_data()
        
        q_tmpl = self.env.get_template("manual/_quarto.yml.j2")
        with open(self.output_dir / "_quarto.yml", "w", encoding='utf-8') as f:
            f.write(q_tmpl.render(self.config))
        
        idx_tmpl = self.env.get_template("manual/index.qmd.j2")
        with open(self.output_dir / "index.qmd", "w", encoding='utf-8') as f:
            f.write(idx_tmpl.render(self.config))
            
        print("📄 Manual QMD files generated successfully using Jinja2.")