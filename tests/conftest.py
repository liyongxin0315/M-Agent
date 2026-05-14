import sys
from pathlib import Path

# Add src/ to Python path so `agentm` package is found
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
