# tools/find_circular_imports.py
"""
Scan the `app/` package for suspicious import patterns and simple cycles.
- Reports any file that imports itself (direct self-import).
- Builds a directed graph of app.* imports and finds simple cycles.
Run: python tools/find_circular_imports.py
"""

import ast
import os
from pathlib import Path
from collections import defaultdict, deque

ROOT = Path(__file__).resolve().parents[1]  # repo root (assumes tools/ is at repo root)
APP_DIR = ROOT / "app"

def find_py_files(base: Path):
    for p in base.rglob("*.py"):
        yield p

def extract_imports(file_path: Path):
    text = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except Exception as e:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module is None:
                # relative import like 'from . import foo' -> record as relative
                module = ""
            level = node.level
            # compute dotted name if possible
            imports.append(("from", module, level))
    return imports

def normalize_import(base_file: Path, imp):
    """
    Normalize an import entry into an app.* module name if applicable.
    Returns None if it doesn't reference app.* modules.
    """
    if isinstance(imp, str):
        name = imp
        if name.startswith("app"):
            return name.split(".")[0] if name == "app" else name
        return None
    elif isinstance(imp, tuple) and imp[0] == "from":
        _, module, level = imp
        # handle explicit from imports: if module begins with 'app' use it
        if module and module.startswith("app"):
            return module
        # handle relative imports: level>0
        if level and level > 0:
            # compute dotted path for base_file
            rel = base_file.relative_to(APP_DIR).with_suffix("")
            parts = rel.parts  # e.g., ('module','submodule')
            # navigate up 'level' levels
            if level <= len(parts):
                target_parts = parts[:len(parts)-level+1]  # +1 because from . import x refers to current package
                if module:
                    target_parts = target_parts + tuple(module.split("."))
                name = "app." + ".".join(target_parts)
                return name
    return None

def build_graph():
    files = list(find_py_files(APP_DIR))
    graph = defaultdict(set)
    file_by_module = {}
    for f in files:
        # module name e.g. app.sub.module
        rel = f.relative_to(APP_DIR).with_suffix("")
        module_name = "app." + ".".join(rel.parts)
        file_by_module[module_name] = f

    for module_name, f in file_by_module.items():
        imports = extract_imports(f)
        for imp in imports:
            norm = normalize_import(f, imp)
            if norm:
                # add edge module_name -> norm (we keep only app.* nodes)
                graph[module_name].add(norm)
    return graph, file_by_module

def find_self_imports(graph):
    self_imports = []
    for mod, deps in graph.items():
        if mod in deps:
            self_imports.append(mod)
    return self_imports

def find_cycles(graph):
    # simple directed cycle detection using DFS
    visited = {}
    stack = []
    cycles = []

    def dfs(node):
        if node in visited:
            return
        path = []
        visited[node] = 1
        stack.append(node)
        path.append(node)
        for neigh in graph.get(node, []):
            if neigh not in visited:
                dfs(neigh)
            elif neigh in stack:
                # found a cycle: neighbors from stack index of neigh to end
                idx = stack.index(neigh)
                cycles.append(stack[idx:] + [neigh])
        stack.pop()

    for n in list(graph.keys()):
        if n not in visited:
            dfs(n)
    # deduplicate cycles
    unique = []
    for c in cycles:
        if c not in unique:
            unique.append(c)
    return unique

def main():
    print(f"Scanning {APP_DIR} for imports...")
    graph, file_by_module = build_graph()
    print(f"Found {len(file_by_module)} app modules.")
    self_imports = find_self_imports(graph)
    if self_imports:
        print("\nDirect self-imports detected (module imports itself):")
        for s in self_imports:
            print(f"  - {s} -> {file_by_module.get(s)}")
    else:
        print("\nNo direct self-imports found.")

    cycles = find_cycles(graph)
    if cycles:
        print("\nPotential import cycles found:")
        for c in cycles:
            print("  Cycle:")
            for node in c:
                print(f"    {node} -> {file_by_module.get(node)}")
    else:
        print("\nNo cycles detected in app.* import graph (simple check).")

    # show modules with high in-degree (hotspots)
    indeg = defaultdict(int)
    for src, deps in graph.items():
        for d in deps:
            indeg[d] += 1
    hotspots = sorted(indeg.items(), key=lambda x: -x[1])[:10]
    if hotspots:
        print("\nTop import targets (modules most referenced by others):")
        for mod, cnt in hotspots:
            print(f"  {mod} referenced by {cnt} modules -> {file_by_module.get(mod)}")

if __name__ == "__main__":
    main()
