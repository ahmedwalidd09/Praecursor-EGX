"""Render the local pages and self-contained HTML exports with one visual theme."""
from pathlib import Path

TEMPLATES = Path(__file__).parent / "templates"


def render_page(name):
    return (TEMPLATES.joinpath(name).read_text(encoding="utf-8")
            .replace("<!-- shared-style -->", "<style>" + TEMPLATES.joinpath("theme.css").read_text(encoding="utf-8") + "</style>")
            .replace("<!-- shared-script -->", "<script>" + TEMPLATES.joinpath("interactions.js").read_text(encoding="utf-8") + "</script>")
            .replace("<!-- dashboard-script -->", "<script>" + TEMPLATES.joinpath("dashboard.js").read_text(encoding="utf-8") + "</script>"))
