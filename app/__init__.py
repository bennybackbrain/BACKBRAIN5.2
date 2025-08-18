"""App package.

FastAPI instance is available as app.main:app. Avoid importing it implicitly here
to keep side-effect free imports for CLI tools (e.g., loader.py) that only need
service utilities.
"""

from typing import List

__all__: List[str] = []
