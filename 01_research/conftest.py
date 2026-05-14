"""Ajoute 01_research/ à sys.path pour que les tests puissent faire `from src... import ...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
