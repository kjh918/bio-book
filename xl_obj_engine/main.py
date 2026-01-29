import pandas as pd
from copy import deepcopy
from openpyxl.utils import get_column_letter # [MODIFIED] 열 문자 계산 유틸 추가
from src.xl_obj_engine.core.engine import ExcelObjectEngine

def run_report_generation():
	engine = ExcelObjectEngine()
		
	# 1. 경로 설정
	template_path = "data/templete.xlsx"
	input_path = "data/input_data.xlsx"
	output_path = "output/final_report.xlsx"

	# 2. 데이터 로드 및 전처리
	# ffill()로 병합된 검체명/일자 등을 채우고, 첫 번째 데이터 행(iloc[1:])부터 시작
	df = pd.read_excel(input_path).ffill()
	df = df.iloc[1:].reset_index(drop=True) 

	samples = []
	# 3행씩 단위를 묶어 샘플 객체 생성
	for i in range(0, len(df), 3):
		chunk = df.iloc[i:i+3]
		if chunk.empty or len(chunk) < 3: break # 3행이 안 되는 자투리 데이터 방지
		
		samples.append({
			"name": str(chunk.iloc[0]["검체명"]),
			"date": str(chunk.iloc[0]["시험일자"]).split(' ')[0], # 시간 제외 날짜만 추출
			"lot": str(chunk.iloc[0]["Plate Lot No."]),
			"results": chunk.iloc[:, 7:16].values.tolist() # UBE2C ~ UBQLN1 데이터 슬라이싱
		})

	# 3. 템플릿 로드 (Style 보존을 위해 엔진 사용)
	base_template_model = engine.read_to_model(template_path)
	base_sheet = base_template_model.sheets[0]
		
	final_sheets = []
		
	# 10개 샘플 단위로 새로운 시트 생성
	for sheet_idx, i in enumerate(range(0, len(samples), 10)):
		chunk_10 = samples[i:i+10]
		
		# [MODIFIED] 시트 이름 결정 로직 통합
		date_str = chunk_10[0]["date"].replace('.', '')
		new_sheet = deepcopy(base_sheet)
		new_sheet.sheet_name = f"Rawdata_{date_str}_{sheet_idx + 1}"
		
		# 공통 헤더 정보 업데이트
		new_sheet.cells["K5"].value = chunk_10[0]["date"]
		new_sheet.cells["S6"].value = chunk_10[0]["lot"]

		for idx, sample in enumerate(chunk_10):
			# A. 검체명 리스트 매핑 (B9 ~ B18)
			new_sheet.cells[f"E{10+idx}"].value = sample["name"]
			
			# B. 결과값 배치 (3개 행 단위 블록)
			# 1-5번 샘플: F45~F59 배치 (57, 58, 59행까지 사용)
			if idx < 5:
				start_row = 45 + (idx * 3)
			# 6-10번 샘플: 60~62행 건너뛰고 F63부터 배치
			else:
				start_row = 63 + ((idx - 5) * 3)
			
			for r_offset in range(3):
				new_sheet.cells[f"F{start_row + r_offset}"].value = sample["name"]
			
			# 유전자별 결과값 주입
			for r_idx, row_values in enumerate(sample["results"]):
				for c_idx, val in enumerate(row_values):
					# [MODIFIED] chr() 대신 get_column_letter를 사용하여 F열(6번째)부터 계산
					col_letter = get_column_letter(7 + c_idx) # F=6, G=7...
					coord = f"{col_letter}{start_row + r_idx}"
					
					if coord in new_sheet.cells:
						new_sheet.cells[coord].value = val
		
		final_sheets.append(new_sheet)

	# 4. 최종 결과물 저장
	if not final_sheets:
		print("Error: No data to export.")
		return

	base_template_model.sheets = final_sheets
	engine.export_from_model(base_template_model, output_path)
	print(f"Report Generated: {len(final_sheets)} sheets created at {output_path}")

if __name__ == "__main__":
	run_report_generation()