"""
Pytest configuration for backend tests.
Adds the backend directory to sys.path so imports work correctly.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
