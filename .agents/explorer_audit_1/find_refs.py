import os

target = "accuracy_history_archive.csv"
skip_dirs = {".git", "__pycache__", ".agents", "venv", ".venv", "node_modules"}

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for f in files:
        if f.endswith(".py") or f.endswith(".md") or f.endswith(".json") or f.endswith(".bat") or f.endswith(".ps1"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                    if target in content:
                        print(f"Found in {path}", flush=True)
            except Exception:
                pass
