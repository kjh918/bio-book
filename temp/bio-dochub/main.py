import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from generators.manual_gen import ManualGenerator
from generators.report_gen import ReportGenerator

def main():
    parser = argparse.ArgumentParser(description="Bio-DocHub: Document Generator")
    parser.add_argument("--mode", choices=['manual', 'report'], required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--build", action="store_true", help="Build Quarto after generating QMD")
    
    args = parser.parse_args()

    if args.mode == 'manual':
        gen = ManualGenerator(config_path=args.config)
    elif args.mode == 'report':
        gen = ReportGenerator(config_path=args.config)
    
    gen.render()
    
    if args.build:
        gen.build_quarto()

if __name__ == "__main__":
    main()