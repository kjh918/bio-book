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
