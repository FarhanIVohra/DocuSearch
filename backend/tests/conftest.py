import os
import sys

# Ensure the backend directory is on sys.path so 'index' package is importable
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
