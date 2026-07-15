import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gencurix_report import (
    ReportBuilder, ReportData, TitlePageData, ChapterItem, SummaryData,
    DividerData, SampleInfoData, ResultItem, ConclusionData,
    Image, Plot, Table,
)

HERE = os.path.dirname(__file__)

# A live matplotlib figure -- NOT saved to disk by the caller.
fig, ax = plt.subplots(figsize=(7, 3))
chroms = [str(i) for i in range(1, 23)] + ["X", "Y"]
zscores = [0.3, -0.2, 0.1, 0.4, -0.1, 0.2, 0.0, -0.3, 0.5, 0.1,
           -0.4, 0.2, 3.8, 0.1, -0.2, 0.3, 0.0, -0.1, 0.2, -0.3,
           0.1, 0.4, 1.2, -0.1]
ax.bar(chroms, zscores, color=["#c0392b" if abs(z) >= 3 else "#2c3e50" for z in zscores])
ax.set_title("Per-chromosome Z-score (live figure, not pre-saved)")

# A live pandas DataFrame -- NOT pre-exported to TSV.
df = pd.DataFrame({
    "Chromosome": ["13", "18", "21", "X"],
    "Z-score": [3.8, 0.123456, -0.3, 0.2],
    "Call": ["Positive (Trisomy 13)", "Normal", "Normal", "Normal (Female)"],
})

data = ReportData(
    title_page=TitlePageData(title="Object-API Test Report", subtitle="Image / Plot / Table objects"),
    chapters=[ChapterItem(name="Introduction"), ChapterItem(name="Results"), ChapterItem(name="Conclusion")],
    summary=SummaryData(purpose=["Testing the Image/Plot/Table convenience constructors"]),
    divider_intro=DividerData(number="01", name="Introduction"),
    workflow_content=Plot(fig, position=(0.7, 1.6), size=(8.5, 3.5)),
    sample_info=SampleInfoData(content=Table(dataframe=df.head(1))),
    divider_results=DividerData(number="02", name="Results"),
    results=[
        ResultItem(title="Live Plot object", content=Plot(fig)),
        ResultItem(title="Live DataFrame object", content=Table(dataframe=df)),
        ResultItem(title="Pre-saved PNG via Image()", content=Image(os.path.join(HERE, "demo_chart.png"))),
    ],
    divider_conclusion=DividerData(number="03", name="Conclusion"),
    conclusion=ConclusionData(
        title="Object API works",
        content_1=Table(headers=["Field", "Value"], rows=[["fig", "matplotlib Figure"], ["df", "pandas DataFrame"]]),
    ),
)

out = os.path.join(HERE, "object_api_example.pptx")
ReportBuilder().build(data, out)
print("Wrote:", out)
