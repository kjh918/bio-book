import os
import yaml
import textwrap
from pathlib import Path
from core.base import BaseGenerator
from core.builder import BookPageBuilder

class ManualGenerator(BaseGenerator):
    def prepare_data(self):
        # 1. source_dir 파싱
        source_src = self.config.get('source_dir', './')
        self.config['source_tree'] = self._get_tree_structure(source_src)
        
        # 2. test_dir 파싱
        test_src = self.config.get('test_dir', '')
        if test_src:
            self.config['test_tree'] = self._get_tree_structure(test_src)

    def _get_tree_structure(self, startpath: str) -> str:
        path = Path(startpath)
        if not path.exists(): return "Directory not found."
        tree_lines = []
        for p in sorted(path.rglob('*')):
            # ✅ 파일은 건너뛰고 오직 폴더(Directory)만 처리
            if not p.is_dir(): 
                continue
                
            if any(part in ['.git', '__pycache__', 'output', '_fastqc'] for part in p.parts): 
                continue
                
            depth = len(p.relative_to(path).parts)
            # 폴더임을 명확히 하기 위해 이름 뒤에 '/'를 붙여줍니다.
            tree_lines.append(f"{'  ' * (depth - 1)}📂 {p.name}/") 
            
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

        # 긴 CMD 명령어를 백슬래시(\)로 줄바꿈 처리 (80자 기준)
        raw_cmd = parsed_obj.get('cmd_line', '').strip()
        if raw_cmd:
            wrapped_lines = textwrap.wrap(raw_cmd, width=80, break_long_words=False, break_on_hyphens=False)
            parsed_obj['cmd_line'] = " \\\n  ".join(wrapped_lines)

        parsed_obj['run_script'] = run_script
        fallback_desc = parsed_obj.get('tool', {}).get('description', '')
        parsed_obj['desc'] = "<br>".join(description_lines) if description_lines else fallback_desc
        
        return [parsed_obj]

    def render(self):
        # 렌더링 전 데이터(Tree 등) 준비
        self.prepare_data()
        builder = BookPageBuilder(self.env, self.output_dir, self.config, template_prefix="manual")
        
        # 1. 고정 페이지 조립
        for page in self.config.get('static_chapters', []):
            builder.add_chapter(page['filename'], page['template'])

        # 2. 동적 Workflow 파트 조립 (새로운 그룹핑 구조 적용)
        workflows = self.config.get('workflows', {})
        tasks_dict = self.config.get('tasks', {})
        
        if workflows:
            for part_title, task_list in workflows.items():
                # 딕셔너리의 Key("1. Pre-processing" 등)를 파트 제목으로 지정
                builder.start_part(part_title) 
                
                # 해당 파트에 속한 task 리스트 순회
                for task_key in task_list:
                    task_info = tasks_dict.get(task_key)
                    if not task_info:
                        print(f"⚠️ [경고] tasks에 '{task_key}' 정의가 누락되었습니다.")
                        continue
                        
                    ext_config_path = task_info.get('config')
                    run_script = task_info.get('script', 'Not Specified')
                    
                    tasks_data = self._load_external_yaml(ext_config_path, run_script) if ext_config_path else []
                    context = {"category_title": task_info.get('title', task_key.upper()), "tasks": tasks_data}
                    
                    fname = task_info.get('filename', f"workflow_{task_key}.qmd")
                    builder.add_chapter(fname, "workflow_chapter.qmd.j2", context)
                    
                builder.end_part() 
            
        # 3. 맺음말 페이지 조립
        for page in self.config.get('footer_chapters', []):
            builder.add_chapter(page['filename'], page['template'])
        
        builder.build()