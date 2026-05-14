"""Met 02_validation/ et 01_research/ sur sys.path pour les imports du gauntlet.

- 02_validation/ sur le path  -> `import gauntlet.pa_rules` etc.
- 01_research/ sur le path    -> `import src.instruments`, `import src.config` etc.
"""
import sys
from pathlib import Path

_GAUNTLET = Path(__file__).resolve().parent           # 02_validation/gauntlet
sys.path.insert(0, str(_GAUNTLET.parent))             # 02_validation/
sys.path.insert(0, str(_GAUNTLET.parents[1] / "01_research"))  # 01_research/
