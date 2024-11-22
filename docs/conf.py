import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("../src"))

project = "pytest-rerunfailures"
copyright = (
    f"2012-{datetime.now(tz=timezone.utc).year}, Leah Klearman and pytest-dev team"
)
author = "Leah Klearman"

extensions = [
    "sphinx.ext.autodoc",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
