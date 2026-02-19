import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from generators.manual_gen import ManualGenerator

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    
    gen = ManualGenerator(args.config)
    gen.render()