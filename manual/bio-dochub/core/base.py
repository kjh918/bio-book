import yaml
from abc import ABC, abstractmethod
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import subprocess

class BaseGenerator(ABC):
    def __init__(self, config_path: str, template_dir: str = None):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        if template_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
            template_path = base_dir / "templates"
        else:
            template_path = Path(template_dir)
            
        self.env = Environment(
            loader=FileSystemLoader(str(template_path)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

    @abstractmethod
    def prepare_data(self):
        pass

    @abstractmethod
    def render(self):
        pass

    def build_quarto(self):
        print(f"🚀 Building Quarto project in {self.output_dir}...")
        try:
            subprocess.run(["quarto", "render", str(self.output_dir)], check=True)
            print("✅ Build completed.")
        except FileNotFoundError:
            print("❌ Error: 'quarto' command not found. Please install Quarto.")