"""
Example: build a full Gencurix analysis report with the gencurix_report package.

Run:
    python example_generate.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gencurix_report import (
    ReportBuilder,
    ReportData,
    TitlePageData,
    ChapterItem,
    SummaryData,
    DividerData,
    SampleInfoData,
    ResultItem,
    ConclusionData,
    ContentBlock,
    TableData,
)

HERE = os.path.dirname(__file__)


def make_demo_chart(path):
    """A stand-in for a real cbNIPT-style per-chromosome Z-score plot."""
    chroms = [str(i) for i in range(1, 23)] + ["X", "Y"]
    zscores = [0.3, -0.2, 0.1, 0.4, -0.1, 0.2, 0.0, -0.3, 0.5, 0.1,
               -0.4, 0.2, 3.8, 0.1, -0.2, 0.3, 0.0, -0.1, 0.2, -0.3,
               0.1, 0.4, 1.2, -0.1]
    colors = ["#c0392b" if abs(z) >= 3 else "#2c3e50" for z in zscores]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.bar(chroms, zscores, color=colors)
    ax.axhline(3, color="gray", linestyle="--", linewidth=0.8)
    ax.axhline(-3, color="gray", linestyle="--", linewidth=0.8)
    ax.set_ylabel("Z-score")
    ax.set_title("Per-chromosome Z-score (sample NIPT-2026-0143)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    chart_path = os.path.join(HERE, "demo_chart.png")
    make_demo_chart(chart_path)

    data = ReportData(
        title_page=TitlePageData(
            title="cbNIPT Analysis Report",
            subtitle="Chromosome 13 Trisomy Detection, Sample NIPT-2026-0143",
            writer="지훈",
            team="Clinical Bioinformatics Team",
            date="2026-07-08",
        ),
        chapters=[
            ChapterItem(name="Introduction & Workflow"),
            ChapterItem(name="Sample Information"),
            ChapterItem(name="Results"),
            ChapterItem(name="Conclusion"),
        ],
        summary=SummaryData(
            purpose=["Non-invasive detection of fetal chromosomal aneuploidy from maternal plasma cfDNA"],
            results=["Chromosome 13 Z-score = 3.8 (positive for trisomy 13)"],
            conclusion=["Result is consistent with Trisomy 13; confirmatory testing recommended"],
            further_study=["Karyotype or CMA confirmation via amniocentesis recommended"],
        ),
        divider_intro=DividerData(number="01", name="Introduction"),
        workflow_content=ContentBlock(bullets=[
            "cfDNA extraction from maternal plasma",
            "Library preparation and low-pass whole-genome sequencing",
            "Read alignment (GRCh38) and GC-bias correction",
            "Bin-level read count normalization and Z-score calculation per chromosome",
        ]),
        sample_info=SampleInfoData(content=ContentBlock(table=TableData(
            headers=["Sample ID", "Gestational Age", "Fetal Fraction", "Total Reads"],
            rows=[["NIPT-2026-0143", "12w3d", "11.2%", "6,842,110"]],
        ))),
        divider_results=DividerData(number="02", name="Results"),
        results=[
            ResultItem(
                title="Chromosome 13 Z-score Overview",
                content=ContentBlock(image_path=chart_path),
            ),
            ResultItem(
                title="Chromosomal Aneuploidy Call Summary",
                content=ContentBlock(table=TableData(
                    headers=["Chromosome", "Z-score", "Call"],
                    rows=[
                        ["13", "3.8", "Positive (Trisomy 13)"],
                        ["18", "0.1", "Normal"],
                        ["21", "-0.3", "Normal"],
                        ["X", "0.2", "Normal (Female)"],
                    ],
                )),
            ),
        ],
        divider_conclusion=DividerData(number="03", name="Conclusion"),
        conclusion=ConclusionData(
            title="Chromosome 13 Trisomy Detected",
            content_1=ContentBlock(bullets=[
                "Z-score of 3.8 on chromosome 13 exceeds the +3.0 clinical threshold",
                "Fetal fraction (11.2%) is within the validated range for reliable calling",
            ]),
            content_2=ContentBlock(bullets=[
                "Recommend confirmatory diagnostic testing (amniocentesis / CVS)",
                "Genetic counseling referral advised prior to further testing",
            ]),
        ),
    )

    out_path = os.path.join(HERE, "cbNIPT_Report_Example.pptx")
    ReportBuilder().build(data, out_path)
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
