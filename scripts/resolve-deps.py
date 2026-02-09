#!/usr/bin/env python3
"""Resolve plugin dependency tree for Claude Code.

Scans installed plugins for a 'dependencies' field in their plugin.json,
builds the full dependency tree, and reports missing plugins with the
commands needed to install them.

Convention: plugins declare dependencies in .claude-plugin/plugin.json:

    {
      "name": "my-plugin",
      "version": "1.0.0",
      "dependencies": {
        "other-plugin": {
          "marketplace": "marketplace-name",
          "source": "owner/repo"
        }
      }
    }

- "marketplace": the local marketplace alias (used in /plugin install name@marketplace)
- "source": GitHub owner/repo for adding the marketplace if not already present
- "version": optional semver constraint (not yet enforced)
"""

import json
import os
import sys
from pathlib import Path

PLUGINS_DIR = Path.home() / ".claude" / "plugins"
INSTALLED_FILE = PLUGINS_DIR / "installed_plugins.json"
MARKETPLACES_FILE = PLUGINS_DIR / "known_marketplaces.json"


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_installed_plugins():
    """Return dict of plugin_name -> {marketplace, version, install_path}."""
    data = load_json(INSTALLED_FILE)
    plugins = {}
    for key, installs in data.get("plugins", {}).items():
        # key format: "plugin-name@marketplace-name"
        if "@" not in key:
            continue
        name, marketplace = key.split("@", 1)
        for install in installs:
            path = install.get("installPath", "")
            version = install.get("version", "")
            plugins[name] = {
                "marketplace": marketplace,
                "version": version,
                "install_path": path,
                "scope": install.get("scope", ""),
                "project_path": install.get("projectPath", ""),
            }
    return plugins


def get_known_marketplaces():
    """Return dict of marketplace_name -> source info."""
    return load_json(MARKETPLACES_FILE)


def read_plugin_json(install_path):
    """Read a plugin's .claude-plugin/plugin.json."""
    pj = Path(install_path) / ".claude-plugin" / "plugin.json"
    return load_json(pj)


def resolve(installed, marketplaces):
    """Walk the dependency tree. Return (tree, missing, marketplace_cmds, install_cmds)."""
    tree = {}  # plugin_name -> list of dependency names
    missing = {}  # dep_name -> {marketplace, source}
    marketplace_cmds = []  # /plugin marketplace add commands
    install_cmds = []  # /plugin install commands

    # Also scan plugins loaded via --plugin-dir (check project .claude/settings*)
    # For now, focus on globally installed plugins

    visited = set()

    def walk(name):
        if name in visited:
            return
        visited.add(name)

        info = installed.get(name)
        if not info:
            return

        pj = read_plugin_json(info["install_path"])
        deps = pj.get("dependencies", {})
        tree[name] = list(deps.keys())

        for dep_name, dep_info in deps.items():
            if isinstance(dep_info, str):
                dep_info = {"marketplace": dep_info}

            if dep_name not in installed:
                missing[dep_name] = dep_info
                mp_name = dep_info.get("marketplace", "")
                source = dep_info.get("source", "")

                # Need to add marketplace?
                if mp_name and mp_name not in marketplaces:
                    if source:
                        cmd = f"/plugin marketplace add {source}"
                        if cmd not in marketplace_cmds:
                            marketplace_cmds.append(cmd)

                # Install command
                if mp_name:
                    install_cmds.append(f"/plugin install {dep_name}@{mp_name}")
            else:
                walk(dep_name)

    for name in list(installed.keys()):
        walk(name)

    return tree, missing, marketplace_cmds, install_cmds


def print_tree(tree, installed):
    """Print a visual dependency tree."""
    if not any(deps for deps in tree.values()):
        print("No dependencies declared by any installed plugin.")
        return

    print("Dependency tree:")
    for name, deps in sorted(tree.items()):
        if deps:
            status = "installed" if name in installed else "MISSING"
            print(f"  {name} ({status})")
            for i, dep in enumerate(deps):
                prefix = "└── " if i == len(deps) - 1 else "├── "
                dep_status = "installed" if dep in installed else "MISSING"
                print(f"    {prefix}{dep} ({dep_status})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "resolve"

    installed = get_installed_plugins()
    marketplaces = get_known_marketplaces()
    tree, missing, mp_cmds, install_cmds = resolve(installed, marketplaces)

    if mode == "tree":
        print_tree(tree, installed)
        return

    if mode == "json":
        print(json.dumps({
            "installed": {k: v["version"] for k, v in installed.items()},
            "tree": tree,
            "missing": list(missing.keys()),
            "marketplace_commands": mp_cmds,
            "install_commands": install_cmds,
        }, indent=2))
        return

    # Default: resolve mode — human-readable output
    print(f"Installed plugins: {len(installed)}")
    for name, info in sorted(installed.items()):
        print(f"  {name} v{info['version']} ({info['marketplace']})")

    print()
    print_tree(tree, installed)

    if missing:
        print(f"\nMissing dependencies: {len(missing)}")
        if mp_cmds:
            print("\nFirst, add missing marketplaces:")
            for cmd in mp_cmds:
                print(f"  {cmd}")
        print("\nThen install missing plugins:")
        for cmd in install_cmds:
            print(f"  {cmd}")
    else:
        print("\nAll dependencies satisfied.")


if __name__ == "__main__":
    main()
