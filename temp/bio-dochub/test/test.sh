#!/bin/bash

echo "🛠️ 1. 테스트용 가상 파이프라인 환경(Mock)을 구성합니다..."

TEST_DIR="test_env"
mkdir -p "$TEST_DIR/scripts"

# 1-1. 가상 파이프라인 코드 작성
cat << 'EOF' > "$TEST_DIR/mock_pipeline.py"
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
EOF

# 1-2. 가상 스크립트 1 (FastQC) - Docstring과 argparse 포함
cat << 'EOF' > "$TEST_DIR/scripts/run_fastqc.py"
"""
이 스크립트는 FastQC를 이용하여 Raw Fastq 파일의 품질을 평가하고 결과를 추출합니다.
"""
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FastQC Runner")
    parser.add_argument('--SeqID', '-s', required=True, help="분석 대상 샘플의 고유 ID")
    parser.add_argument('--RawFastqDir', '-r', required=True, help="Raw Fastq 파일이 존재하는 디렉토리 경로")
    parser.add_argument('--Threads', '-t', default=4, help="FastQC 분석에 할당할 코어 수")
    args = parser.parse_args()
EOF

# 1-3. 가상 스크립트 2 (BWA)
cat << 'EOF' > "$TEST_DIR/scripts/run_bwa.py"
"""
BWA-MEM 알고리즘을 사용하여 Reference Genome에 Read를 매핑하고 BAM 파일을 생성합니다.
"""
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BWA Alignment Runner")
    parser.add_argument('--SeqID', required=True, help="샘플 ID")
    parser.add_argument('--TrimFastqDir', required=True, help="Trimmed Fastq 디렉토리")
    parser.add_argument('--ReferenceFasta', required=True, help="hg38 참조 유전체 경로")
    args = parser.parse_args()
EOF

echo "📝 2. 테스트용 YAML Schema 설정을 업데이트합니다..."

# [MODIFIED] 동적으로 변경 가능한 변수(경로)를 실제 테스트 디렉토리로 지정
cat << 'EOF' > "test_manual_conf.yaml"
type: manual
project_name: "Mock cbNIPT Pipeline"
version: "0.1.0-test"
author: "Test User"
date: "2026-02-19"
source_dir: "./test_env"
pipeline_script: "./test_env/mock_pipeline.py"
scripts_dir: "./test_env/scripts"
EOF

echo "🚀 3. Document Generator(main.py)를 실행합니다..."

# 메인 시스템 구동
python3 /storage/home/jhkim/scripts/bio-book/temp/bio-dochub/main.py --mode manual --config test_manual_conf.yaml

echo "=========================================================="
echo "✅ 4. 생성된 마크다운 문서 (output/index.qmd) 내용 확인:"
echo "=========================================================="
cat output/index.qmd
echo "=========================================================="