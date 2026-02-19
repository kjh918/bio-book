import ast
from pathlib import Path
from typing import List, Dict, Any

def parse_script_details_from_ast(script_path: Path) -> Dict[str, Any]:
    # [MODIFIED] argparse 추출뿐만 아니라 스크립트 최상단의 docstring도 함께 추출하도록 확장
    result = {'args': [], 'docstring': ''}
    if not script_path or not script_path.exists():
        return result

    with open(script_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return result

    # 1. Docstring 추출
    doc = ast.get_docstring(tree)
    if doc:
        result['docstring'] = doc.strip()

    # 2. argparse 추출
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument':
            arg_data = {'flags': [], 'help': '', 'default': '', 'required': False}
            
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    arg_data['flags'].append(arg.value)
                    
            for kw in node.keywords:
                if kw.arg == 'help' and isinstance(kw.value, ast.Constant):
                    arg_data['help'] = kw.value.value
                elif kw.arg == 'default' and isinstance(kw.value, ast.Constant):
                    arg_data['default'] = str(kw.value.value)
                elif kw.arg == 'required' and isinstance(kw.value, ast.Constant):
                    arg_data['required'] = kw.value.value
            
            if arg_data['flags']:
                arg_data['flags_str'] = ", ".join(arg_data['flags'])
                result['args'].append(arg_data)
                
    return result

def extract_workflow_from_ast(pipeline_path: str, scripts_base_dir: str) -> List[Dict[str, Any]]:
    path = Path(pipeline_path)
    if not path.exists():
        return [{"name": "Error", "desc": f"Pipeline not found: {pipeline_path}", "args": []}]

    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    workflow = []
    scripts_dir = Path(scripts_base_dir)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Task':
            task_name = "Unknown"
            script_name = ""
            
            for kw in node.keywords:
                if kw.arg == 'name' and isinstance(kw.value, ast.Constant):
                    task_name = kw.value.value
                elif kw.arg == 'runner_path':
                    if isinstance(kw.value, ast.BinOp) and isinstance(kw.value.right, ast.Constant):
                        script_name = kw.value.right.value
                    elif isinstance(kw.value, ast.Constant):
                        script_name = kw.value.value

            target_script_path = scripts_dir / script_name if script_name else None
            script_details = parse_script_details_from_ast(target_script_path)

            workflow.append({
                "name": task_name,
                "script": script_name,
                "desc": script_details['docstring'], # 파일 내부의 설명문을 사용
                "args": script_details['args']
            })
                
    return workflow