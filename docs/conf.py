import os
import sys
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

project = "Сервис модерации комментариев"
author = "Команда разработки"
copyright = f"{datetime.utcnow():%Y}, {author}"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosectionlabel",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

try:
    import sphinx_rtd_theme  # type: ignore

    html_theme = "sphinx_rtd_theme"
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]  # deprecated but keeps compatibility
except ImportError:  # pragma: no cover - fallback when тема не установлена
    html_theme = "alabaster"

html_static_path = ["_static"]

language = "ru"

autosectionlabel_prefix_document = True
