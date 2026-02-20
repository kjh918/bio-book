import os
import yaml
import textwrap
from pathlib import Path
from core.base import BaseGenerator
from core.builder import BookPageBuilder

class ManualGenerator(BaseGenerator):
    def prepare_data(self):
        target_src = self.config.get('source_dir', './')
        self.config['tree_structure'] = self._get_tree_structure(target_src)

    def _get_tree_structure(self, startpath: str) -> str:
        path = Path(startpath)
        if not path.exists(): return "Directory not found."
        tree_lines = []
        for p in sorted(path.rglob('*')):
            if any(part in ['.git', '__pycache__', 'output'] for part in p.parts): continue
            depth = len(p.relative_to(path).parts)
            tree_lines.append(f"{'  ' * (depth - 1)}* {p.name}")
        return "\n".join(tree_lines) if tree_lines else "Empty directory."
    
    def _load_external_yaml(self, filepath: str, run_script: str) -> list:
        if not filepath: return []
            
        real_path = Path(os.path.expanduser(filepath)).resolve()
        if not real_path.exists():
            print(f"❌ [에러] 외부 YAML 파일을 찾을 수 없습니다: {real_path}")
            return []

        description_lines = []
        with open(real_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#'):
                    clean_line = stripped.lstrip('#').strip()
                    if clean_line and not clean_line.startswith('====') and not clean_line.startswith('----'):
                        description_lines.append(clean_line)
                elif stripped:
                    break

        with open(real_path, 'r', encoding='utf-8') as f:
            parsed_obj = yaml.safe_load(f)

        if not parsed_obj:
            return []

        # [NEW] 긴 CMD 명령어를 백슬래시(\)로 줄바꿈 처리 (80자 기준)
        raw_cmd = parsed_obj.get('cmd_line', '').strip()
        if raw_cmd:
            wrapped_lines = textwrap.wrap(raw_cmd, width=80, break_long_words=False, break_on_hyphens=False)
            parsed_obj['cmd_line'] = " \\\n  ".join(wrapped_lines) # 줄바꿈 후 들여쓰기 2칸 추가

        parsed_obj['run_script'] = run_script
        fallback_desc = parsed_obj.get('tool', {}).get('description', '')
        parsed_obj['desc'] = "<br>".join(description_lines) if description_lines else fallback_desc
        
        return [parsed_obj]

    def render(self):
        self.prepare_data()
        builder = BookPageBuilder(self.env, self.output_dir, self.config, template_prefix="manual")
        
        # 1. 고정 페이지 조립
        for page in self.config.get('static_chapters', []):
            builder.add_chapter(page['filename'], page['template'])
        
        # 2. 동적 Workflow 파트 조립
        workflows = self.config.get('workflows', {})
        if workflows:
            builder.start_part("Pipeline Workflows") 
            for cat_key, cat_data in workflows.items():
                ext_config_path = cat_data.get('config')
                run_script = cat_data.get('script', 'Not Specified')
                
                tasks_data = self._load_external_yaml(ext_config_path, run_script) if ext_config_path else []
                context = {"category_title": cat_data.get('title', cat_key.upper()), "tasks": tasks_data}
                
                fname = cat_data.get('filename', f"workflow_{cat_key}.qmd")
                builder.add_chapter(fname, "workflow_chapter.qmd.j2", context)
            builder.end_part() 
            
        # 3. 맺음말 페이지 조립
        for page in self.config.get('footer_chapters', []):
            builder.add_chapter(page['filename'], page['template'])
        
        builder.build()