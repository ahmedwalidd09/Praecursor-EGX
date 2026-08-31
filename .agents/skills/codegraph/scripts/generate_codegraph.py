import ast
import json
import sys
from pathlib import Path

def analyze_python_file(file_path: Path, root: Path):
    rel_path = str(file_path.relative_to(root)).replace("\\", "/")
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        return {'file': rel_path, 'error': str(e)}

    classes = []
    functions = []
    imports = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append(name.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            for name in node.names:
                imports.append(f"{mod}.{name.name}" if mod else name.name)
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            doc = ast.get_docstring(node) or ''
            classes.append({
                'name': node.name,
                'methods': methods,
                'doc': doc.split('\n')[0] if doc else '',
                'line': node.lineno
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ''
            functions.append({
                'name': node.name,
                'args': [a.arg for a in node.args.args],
                'doc': doc.split('\n')[0] if doc else '',
                'line': node.lineno
            })

    return {
        'file': rel_path,
        'classes': classes,
        'functions': functions,
        'imports': imports,
        'lines': len(content.splitlines())
    }

def build_codegraph(repo_path: Path):
    graph = {'root': str(repo_path), 'modules': {}, 'symbol_index': {}}
    for base in [repo_path / 'src', repo_path / 'tools', repo_path / 'tests']:
        if not base.exists():
            continue
        for py_file in base.rglob('*.py'):
            info = analyze_python_file(py_file, repo_path)
            graph['modules'][info['file']] = info
            for c in info.get('classes', []):
                graph['symbol_index'][c['name']] = {'type': 'class', 'file': info['file'], 'line': c['line']}
            for f in info.get('functions', []):
                graph['symbol_index'][f['name']] = {'type': 'function', 'file': info['file'], 'line': f['line']}
    return graph

if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    graph = build_codegraph(root)
    out_file = root / 'reports' / 'codegraph.json' if (root / 'reports').exists() else Path('codegraph.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2)
    print(f"[CodeGraph] Indexed {len(graph['modules'])} modules, {len(graph['symbol_index'])} symbols to {out_file}")
