"""Locations used by the probe scripts. PATHWAYS_ROOT holds runs and analyses (default runs/probes);
MANIPSCOPE_ROOT is this repository. MODELS_ROOT holds the pi0.5 and Motus checkpoints and repositories;
SIM_PYTHON, PI05_PYTHON and MOTUS_PYTHON select the interpreters (default: the current one)."""
import os
import sys
from pathlib import Path
TOOLS = Path(__file__).resolve().parent
REPO = Path(os.environ.get('MANIPSCOPE_ROOT', TOOLS.parents[1]))
R = Path(os.environ.get('PATHWAYS_ROOT', REPO / 'runs/probes')).resolve()
B = Path(os.environ.get('MODELS_ROOT', REPO / 'models'))
SIM_PYTHON = os.environ.get('SIM_PYTHON', sys.executable)
def python_for(kind): return os.environ.get(kind.upper() + '_PYTHON', sys.executable)
