from core.base import BaseGenerator
from core.builder import BookPageBuilder
from pathlib import Path

class ManualGenerator(BaseGenerator):
    def prepare_data(self):
        target_src = self.config.get('source_dir', './')
        self.config['tree_structure'] = self._get_tree_structure(target_src)

    def _get_tree_structure(self, startpath: str) -> str:
        path = Path(startpath)
        if not path.exists():
            return "Directory not found."
            
        tree_lines = []
        for p in sorted(path.rglob('*')):
            if any(part in ['.git', '__pycache__', 'output'] for part in p.parts):
                continue
            depth = len(p.relative_to(path).parts)
            spacer = '  ' * (depth - 1)
            tree_lines.append(f"{spacer}* {p.name}")
        return "\n".join(tree_lines) if tree_lines else "Empty directory."

    def render(self):
        self.prepare_data()
        
        # Book Builder 객체 초기화
        builder = BookPageBuilder(env=self.env, output_dir=self.output_dir, meta_config=self.config)
        
        # 1. 서론 및 고정 페이지 조립
        builder.add_chapter(filename="index.qmd", template="index.qmd.j2")
        builder.add_chapter(filename="01_architecture.qmd", template="01_architecture.qmd.j2")
        builder.add_chapter(filename="02_execution.qmd", template="02_execution.qmd.j2")
        
        # 2. YAML 파싱 및 Workflow 동적 페이지 조립
        workflows = self.config.get('workflows', {})
        if workflows:
            builder.start_part("Pipeline Workflows") # 사이드바 파트 그룹핑 시작
            
            for category_key, category_data in workflows.items():
                filename = category_data.get('filename', f"workflow_{category_key}.qmd")
                context = {
                    "category_title": category_data.get('title', category_key.upper()),
                    "tasks": category_data.get('tasks', [])
                }
                # 공통 템플릿(workflow_chapter)을 재사용하여 다중 페이지 생성
                builder.add_chapter(filename=filename, template="workflow_chapter.qmd.j2", context=context)
                
            builder.end_part() # 파트 묶음 종료
            
        # 3. 마무리 페이지 조립
        builder.add_chapter(filename="06_scaling.qmd", template="06_scaling.qmd.j2")
        
        # 전체 Book 렌더링 실행
        builder.build()