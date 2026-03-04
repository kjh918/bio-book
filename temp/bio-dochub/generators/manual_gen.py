import os
import yaml
import textwrap
import argparse
import importlib.util
from pathlib import Path
from core.base import BaseGenerator
from core.builder import BookPageBuilder

class ManualGenerator(BaseGenerator):

    def _extract_arguments(self) -> list:
        """source_dir 경로에서 run_pipeline.py를 동적으로 읽어와 argparse 옵션을 추출합니다."""
        
        # 1. config에서 source_dir을 가져와 스크립트 절대 경로 완성
        source_dir = self.config.get('source_dir', './')
        script_path = os.path.join(source_dir, 'run_pipeline.py')
        
        if not os.path.exists(script_path):
            print(f"⚠️ [경고] 매뉴얼 생성 실패 - 스크립트를 찾을 수 없습니다: {script_path}")
            return []
            
        # 2. importlib을 사용하여 파이썬 모듈로 동적 로드
        try:
            spec = importlib.util.spec_from_file_location("dynamic_run_pipeline", script_path)
            if spec is None or spec.loader is None:
                print(f"❌ [에러] 모듈 스펙을 생성할 수 없습니다: {script_path}")
                return []
                
            run_pipeline_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(run_pipeline_module)
            
            # 모듈 안에서 get_parser 함수 꺼내기
            if not hasattr(run_pipeline_module, 'get_parser'):
                print(f"⚠️ [경고] {script_path} 모듈 내에 get_parser() 함수가 정의되어 있지 않습니다.")
                return []
                
            parser = run_pipeline_module.get_parser()
            
        except Exception as e:
            print(f"❌ [에러] {script_path} 모듈 동적 로드 중 오류 발생: {e}")
            return []

        # 3. 파서에서 그룹별 인자(Arguments) 데이터 추출
        groups_data = []
        for group in parser._action_groups:
            # 기본 도움말 옵션 및 메타 그룹은 제외
            if group.title in ["options", "positional arguments", "optional arguments"]: 
                continue 
            
            group_info = {
                "category": group.title,
                "description": group.description or "",
                "items": []
            }
            
            for action in group._group_actions:
                if action.dest == "help": 
                    continue
                
                flags = action.option_strings
                short_arg = [f for f in flags if len(f) <= 2]
                long_arg = [f for f in flags if len(f) > 2]
                
                # argparse.SUPPRESS는 숨김 처리된 옵션이므로 빈 값으로 처리
                default_val = str(action.default) if action.default is not None and action.default != argparse.SUPPRESS else ""
                desc = f"**(필수)** {action.help}" if action.required else (action.help or "")

                group_info["items"].append({
                    "arg": long_arg[0] if long_arg else (short_arg[0] if short_arg else ""),
                    "short": short_arg[0] if short_arg else "",
                    "default": default_val,
                    "desc": desc
                })
                
            if group_info["items"]:
                groups_data.append(group_info)
                
        return groups_data

    def _get_tree_structure(self, startpath: str) -> str:
        """지정된 디렉토리의 하위 폴더 및 파일 트리를 텍스트로 반환합니다."""
        path = Path(startpath)
        if not path.exists(): 
            return "Directory not found."
            
        tree_lines = []
        for p in sorted(path.rglob('*')):
            # 무시할 디렉토리 패턴
            if any(part in ['.git', '__pycache__', 'output', '_fastqc'] for part in p.parts): 
                continue
                
            depth = len(p.relative_to(path).parts)
            # 확장자가 있으면(.) 파일로 취급, 없으면 폴더로 취급 (간단한 판별법)
            if len(p.name.split('.')) >= 2:
                tree_lines.append(f"{'  ' * (depth - 1)}📄 {p.name}") 
            else:
                tree_lines.append(f"{'  ' * (depth - 1)}📂 {p.name}") 
            
        return "\n".join(tree_lines) if tree_lines else "Empty directory."

    def _load_external_yaml(self, filepath: str, run_script: str) -> list:
        """Task 명세가 담긴 외부 YAML 파일을 로드하여 파싱합니다."""
        if not filepath: 
            return []
            
        real_path = Path(os.path.expanduser(filepath)).resolve()
        if not real_path.exists():
            print(f"❌ [에러] 외부 YAML 파일을 찾을 수 없습니다: {real_path}")
            return []

        # YAML 파일 상단의 주석(#) 블록을 읽어서 description으로 활용
        description_lines = []
        with open(real_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#'):
                    clean_line = stripped.lstrip('#').strip()
                    if clean_line and not clean_line.startswith('====') and not clean_line.startswith('----'):
                        description_lines.append(clean_line)
                elif stripped:
                    break # 주석이 끝나고 실제 데이터가 시작되면 중단

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

    def prepare_data(self):
        """렌더링에 필요한 모든 데이터를 수집하여 self.config에 세팅합니다."""
        # 1. source_dir 파싱
        source_src = self.config.get('source_dir', './')
        self.config['source_tree'] = self._get_tree_structure(source_src)
        
        # 2. test_dir 파싱
        test_src = self.config.get('test_dir', '')
        if test_src:
            self.config['test_tree'] = self._get_tree_structure(test_src)

        # 3. 매뉴얼(Manual)용 동적 데이터 준비 및 병합
        manual_data = self.config.get('manual', {})
        manual_data['arguments'] = self._extract_arguments()
        
        manual_data['output_tree'] = """[workpath]
├── [sample_id]
│   ├── [task_output]/    # pipeline에 설정된 task들의 결과 저장 디렉토리 
│   ├── logs/             # 개별 샘플의 전체 log 결과 
│   │   ├── [task1]/      # task 별 error, out, sh 파일 정리
│   │   │   ├── [task1].stderr  # task error log 파일
│   │   │   ├── [task1].stdout  # task out log 파일
│   │   │   └── [task1].sh      # task 실행 bash script 파일
│   ├── qc/               # 각종 QC 결과 파일들 (GATK, Picard, Mosdepth 등)
│   └── tmp/              # 분석 중 생성되는 임시 파일들
└── logs/                 # 파이프라인 전체 실행 로그
    └── [date]/
        └── [total_process_script].sh # 전체 task에 대한 qsub 명령어 및 job_id 기록"""

        # 완성된 데이터를 config에 병합 (Jinja2 템플릿으로 넘어감)
        self.config['manual'] = manual_data

    def render(self):
        """수집된 데이터를 바탕으로 Quarto 문서 체계를 빌드합니다."""
        # 렌더링 전 데이터 완벽 세팅
        self.prepare_data()
        
        builder = BookPageBuilder(self.env, self.output_dir, self.config, template_prefix="manual")
        
        # 1. 고정 페이지(index, setup, manual, architecture 등) 조립
        for page in self.config.get('static_chapters', []):
            builder.add_chapter(page['filename'], page['template'])

        # 2. 동적 Workflow 파트 조립
        workflows = self.config.get('workflows', {})
        tasks_dict = self.config.get('tasks', {})
        
        if workflows:
            for part_title, task_list in workflows.items():
                builder.start_part(part_title) 
                
                for task_key in task_list:
                    task_info = tasks_dict.get(task_key)
                    if not task_info:
                        print(f"⚠️ [경고] tasks 딕셔너리에 '{task_key}' 정의가 누락되었습니다.")
                        continue
                        
                    ext_config_path = task_info.get('config')
                    run_script = task_info.get('script', 'Not Specified')
                    
                    tasks_data = self._load_external_yaml(ext_config_path, run_script) if ext_config_path else []
                    context = {"category_title": task_info.get('title', task_key.upper()), "tasks": tasks_data}
                    
                    fname = task_info.get('filename', f"workflow_{task_key}.qmd")
                    builder.add_chapter(fname, "workflow_chapter.qmd.j2", context)
                    
                builder.end_part() 
            
        # 3. 맺음말(Footer) 페이지 조립
        for page in self.config.get('footer_chapters', []):
            builder.add_chapter(page['filename'], page['template'])
        
        # 실제 파일 생성
        builder.build()