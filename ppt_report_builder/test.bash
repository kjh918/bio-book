python generate_report.py report_config.yaml                              # 기본: <yaml이름>.pptx로 저장
python generate_report.py report_config.yaml -o output.pptx               # 출력 경로 지정
python generate_report.py report_config.yaml --template MyTemplate.pptx   # 다른 템플릿 사용
python generate_report.py report_config.yaml --dry-run                    # 실제 생성 없이 검증만