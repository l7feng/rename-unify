"""Read per-tool release versions from the packaged Web manifest."""
import json
import re
from pathlib import Path
from shell.httpd import WEB_DIR

def tool_version(tool):
    versions = json.loads((Path(WEB_DIR) / "app-versions.json").read_text(encoding="utf-8"))
    version = versions[tool]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid application version")
    return version
