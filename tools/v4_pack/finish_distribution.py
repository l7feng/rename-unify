"""Apply the same release-file policy to each independent application."""
from pathlib import Path
import importlib.metadata
import json
import shutil
import sys


def finish_distribution(app, repo, key):
    app, repo = Path(app), Path(repo)
    for filename in ("使用说明.md", "Install-Dependencies.ps1", "Install-Dependencies.cmd"):
        shutil.copy2(repo / "packaging" / filename, app / filename)
    shutil.copy2(repo / "LICENSE", app / "LICENSE")
    for other, page, script in (("pt", "index.html", "app.js"),
                                ("jy", "jy.html", "jy.js"),
                                ("re", "re.html", "re.js")):
        if other != key:
            for path in (app / "_internal/web" / page, app / "_internal/web/js" / script):
                if path.exists():
                    path.unlink()
    for folder in (app / "_internal/api", app / "_internal/shell"):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in (".pyc", ".pyo"):
                path.unlink()
    third = app / "THIRD_PARTY"
    third.mkdir(exist_ok=True)
    records = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        for relative in distribution.files or ():
            if ".." in relative.parts:
                continue
            if any("license" in part.lower() or part.lower() in ("copying", "notice", "authors")
                   for part in relative.parts):
                source = Path(distribution.locate_file(relative))
                if source.is_file():
                    target = third / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        records.append({"name": name, "version": distribution.version})
    (third / "build-dependencies.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", third / "Python-LICENSE.txt")
