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
