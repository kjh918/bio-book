import os
from pathlib import Path

scripts = Path(os.path.dirname(__file__)) / 'scripts'

# AST 파싱용 더미 구조
tasks = [
    Task(
        name="fastqc",
        runner_path=scripts / "run_fastqc.py",
        spec={"Threads": 4}
    ),
    Task(
        name="bwa_align",
        runner_path=scripts / "run_bwa.py",
        spec={"Threads": 8}
    )
]
