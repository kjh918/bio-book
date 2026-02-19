from core.base import BaseGenerator

class ReportGenerator(BaseGenerator):
    def prepare_data(self):
        self.config.setdefault('stats', {
            'total_reads': "N/A",
            'mapping_rate': "N/A"
        })

    def render(self):
        self.prepare_data()
        
        tmpl = self.env.get_template("report/summary.qmd.j2")
        output_file = self.output_dir / f"{self.config.get('sample_id', 'report')}.qmd"
        with open(output_file, "w", encoding='utf-8') as f:
            f.write(tmpl.render(self.config))
            
        print("📊 Report QMD generated successfully.")