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
          "source": "owner/repo",
          "version": ">=0.5.0"
        }
      }
    }

- "marketplace": the local marketplace alias (used in /plugin install name@marketplace)
- "source": GitHub owner/repo for adding the marketplace if not already present
- "version": semver constraint — supports =, >=, <=, >, <, ^, ~, and space-separated ranges
"""

import json
import re
import sys
from pathlib import Path

PLUGINS_DIR = Path.home() / ".claude" / "plugins"
INSTALLED_FILE = PLUGINS_DIR / "installed_plugins.json"
MARKETPLACES_FILE = PLUGINS_DIR / "known_marketplaces.json"


# ---------------------------------------------------------------------------
# Semver parsing and comparison
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z\-.]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z\-.]+))?$"
)


def parse_version(v):
    """Parse a semver string into (major, minor, patch, pre) tuple.

    Pre-release is stored as a tuple of segments for proper ordering.
    A release version (no pre) sorts higher than any pre-release of
    the same numeric version, per semver spec.
    """
    v = v.strip().lstrip("v")
    m = _SEMVER_RE.match(v)
    if not m:
        return None
    major, minor, patch = int(m.group("major")), int(m.group("minor")), int(m.group("patch"))
    pre_str = m.group("pre")
    if pre_str:
        # Split segments; numeric segments compare as ints, others as strings
        pre = tuple(int(s) if s.isdigit() else s for s in pre_str.split("."))
    else:
        pre = None
    return (major, minor, patch, pre)


def _version_key(parsed):
    """Return a sort key for a parsed version tuple.

    Semver: 1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-beta < 1.0.0
    We achieve this by sorting (major, minor, patch, pre_sort_key) where
    no pre-release gets a high sentinel value.
    """
    major, minor, patch, pre = parsed
    if pre is None:
        # No pre-release — sorts after any pre-release of same numeric version
        return (major, minor, patch, (1,))
    else:
        # Pre-release: each segment compared; ints < strings per semver
        normalized = []
        for s in pre:
            if isinstance(s, int):
                normalized.append((0, s, ""))
            else:
                normalized.append((1, 0, s))
        return (major, minor, patch, (0,) + tuple(normalized))


def version_cmp(a, b):
    """Compare two parsed versions. Returns -1, 0, or 1."""
    ka, kb = _version_key(a), _version_key(b)
    return (ka > kb) - (ka < kb)


def version_gte(a, b):
    return version_cmp(a, b) >= 0


def version_lte(a, b):
    return version_cmp(a, b) <= 0


def version_gt(a, b):
    return version_cmp(a, b) > 0


def version_lt(a, b):
    return version_cmp(a, b) < 0


def version_eq(a, b):
    return version_cmp(a, b) == 0


# ---------------------------------------------------------------------------
# Constraint parsing and matching
# ---------------------------------------------------------------------------

_CONSTRAINT_RE = re.compile(
    r"(?P<op>[>=<^~!]*)\s*(?P<ver>v?(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z\-.]+)?(?:\+[0-9A-Za-z\-.]+)?)"
)


def parse_constraint(spec):
    """Parse a version constraint string into a list of (op, parsed_version).

    Supports:
      "1.2.3"          → exact match (=1.2.3)
      ">=1.2.3"        → greater than or equal
      ">1.2.3"         → strictly greater
      "<=1.2.3"        → less than or equal
      "<1.2.3"         → strictly less
      "!=1.2.3"        → not equal
      "^1.2.3"         → compatible (>=1.2.3, <2.0.0; ^0.2.3 → >=0.2.3, <0.3.0)
      "~1.2.3"         → approximate (>=1.2.3, <1.3.0)
      ">=1.0.0 <2.0.0" → space-separated AND of constraints
    """
    if not spec or not spec.strip():
        return []

    constraints = []
    for m in _CONSTRAINT_RE.finditer(spec):
        op = m.group("op") or "="
        ver = parse_version(m.group("ver"))
        if ver is None:
            continue

        major, minor, patch, pre = ver

        if op in ("=", "=="):
            constraints.append(("=", ver))
        elif op == ">=":
            constraints.append((">=", ver))
        elif op == ">":
            constraints.append((">", ver))
        elif op == "<=":
            constraints.append(("<=", ver))
        elif op == "<":
            constraints.append(("<", ver))
        elif op == "!=":
            constraints.append(("!=", ver))
        elif op == "^":
            # Caret: >=ver, <next_major (or <next_minor if major==0)
            constraints.append((">=", ver))
            if major == 0:
                constraints.append(("<", (0, minor + 1, 0, None)))
            else:
                constraints.append(("<", (major + 1, 0, 0, None)))
        elif op == "~":
            # Tilde: >=ver, <next_minor
            constraints.append((">=", ver))
            constraints.append(("<", (major, minor + 1, 0, None)))
        else:
            # Unknown op, treat as exact
            constraints.append(("=", ver))

    return constraints


def satisfies(version_str, constraint_spec):
    """Check if version_str satisfies the constraint_spec.

    Returns (satisfied: bool, reason: str).
    Empty constraint always satisfied.
    """
    if not constraint_spec or not constraint_spec.strip():
        return True, ""

    ver = parse_version(version_str)
    if ver is None:
        return False, f"cannot parse version '{version_str}'"

    constraints = parse_constraint(constraint_spec)
    if not constraints:
        return False, f"cannot parse constraint '{constraint_spec}'"

    ops = {
        "=": version_eq,
        ">=": version_gte,
        ">": version_gt,
        "<=": version_lte,
        "<": version_lt,
        "!=": lambda a, b: not version_eq(a, b),
    }

    for op, target in constraints:
        fn = ops.get(op)
        if fn and not fn(ver, target):
            tv = format_version(target)
            return False, f"installed {version_str} does not satisfy {op}{tv}"

    return True, ""


def format_version(parsed):
    """Format a parsed version tuple back to a string."""
    major, minor, patch, pre = parsed
    s = f"{major}.{minor}.{patch}"
    if pre:
        s += "-" + ".".join(str(p) for p in pre)
    return s


# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

def resolve(installed, marketplaces):
    """Walk the dependency tree.

    Returns (tree, missing, version_mismatches, cycles, marketplace_cmds, install_cmds, update_cmds).
    """
    tree = {}  # plugin_name -> list of dependency names
    missing = {}  # dep_name -> {marketplace, source}
    mismatches = []  # list of {plugin, dependency, installed, constraint, reason}
    cycles = []  # list of cycle descriptions (e.g., "a -> b -> a")
    marketplace_cmds = []
    install_cmds = []
    update_cmds = []  # /plugin update commands for version mismatches

    resolved = set()
    in_progress = set()

    def walk(name, path=None):
        if path is None:
            path = []

        if name in resolved:
            return
        if name in in_progress:
            cycle_start = path.index(name)
            cycle = path[cycle_start:] + [name]
            cycles.append(" -> ".join(cycle))
            return

        info = installed.get(name)
        if not info:
            return

        in_progress.add(name)

        pj = read_plugin_json(info["install_path"])
        deps = pj.get("dependencies", {})
        tree[name] = list(deps.keys())

        for dep_name, dep_info in deps.items():
            if isinstance(dep_info, str):
                dep_info = {"marketplace": dep_info}

            if dep_name == name:
                continue

            if dep_name not in installed:
                missing[dep_name] = dep_info
                mp_name = dep_info.get("marketplace", "")
                source = dep_info.get("source", "")

                if mp_name and mp_name not in marketplaces:
                    if source:
                        cmd = f"/plugin marketplace add {source}"
                        if cmd not in marketplace_cmds:
                            marketplace_cmds.append(cmd)

                if mp_name:
                    cmd = f"/plugin install {dep_name}@{mp_name}"
                    if cmd not in install_cmds:
                        install_cmds.append(cmd)
            else:
                # Plugin is installed — check version constraint
                constraint = dep_info.get("version", "")
                if constraint:
                    dep_version = installed[dep_name]["version"]
                    ok, reason = satisfies(dep_version, constraint)
                    if not ok:
                        mismatches.append({
                            "plugin": name,
                            "dependency": dep_name,
                            "installed": dep_version,
                            "constraint": constraint,
                            "reason": reason,
                        })
                        mp_name = installed[dep_name]["marketplace"]
                        cmd = f"/plugin update {dep_name}@{mp_name}"
                        if cmd not in update_cmds:
                            update_cmds.append(cmd)

                walk(dep_name, path + [name])

        in_progress.discard(name)
        resolved.add(name)

    for name in list(installed.keys()):
        walk(name)

    return tree, missing, mismatches, cycles, marketplace_cmds, install_cmds, update_cmds


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_tree(tree, installed, mismatches=None):
    """Print a visual dependency tree."""
    if not any(deps for deps in tree.values()):
        print("No dependencies declared by any installed plugin.")
        return

    mismatch_set = set()
    if mismatches:
        for mm in mismatches:
            mismatch_set.add((mm["plugin"], mm["dependency"]))

    print("Dependency tree:")
    for name, deps in sorted(tree.items()):
        if deps:
            status = "installed" if name in installed else "MISSING"
            print(f"  {name} ({status})")
            for i, dep in enumerate(deps):
                prefix = "└── " if i == len(deps) - 1 else "├── "
                if dep not in installed:
                    dep_status = "MISSING"
                elif (name, dep) in mismatch_set:
                    dep_status = f"v{installed[dep]['version']} OUTDATED"
                else:
                    dep_status = f"v{installed[dep]['version']}"
                print(f"    {prefix}{dep} ({dep_status})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "resolve"

    installed = get_installed_plugins()
    marketplaces = get_known_marketplaces()
    tree, missing, mismatches, cycles, mp_cmds, install_cmds, update_cmds = resolve(
        installed, marketplaces
    )

    if mode == "tree":
        print_tree(tree, installed, mismatches)
        if cycles:
            print(f"\nWarning: {len(cycles)} dependency cycle(s) detected:")
            for c in cycles:
                print(f"  {c}")
        return

    if mode == "json":
        print(json.dumps({
            "installed": {k: v["version"] for k, v in installed.items()},
            "tree": tree,
            "missing": list(missing.keys()),
            "version_mismatches": mismatches,
            "cycles": cycles,
            "marketplace_commands": mp_cmds,
            "install_commands": install_cmds,
            "update_commands": update_cmds,
        }, indent=2))
        return

    # Default: resolve mode
    print(f"Installed plugins: {len(installed)}")
    for name, info in sorted(installed.items()):
        print(f"  {name} v{info['version']} ({info['marketplace']})")

    print()
    print_tree(tree, installed, mismatches)

    if cycles:
        print(f"\nWarning: {len(cycles)} dependency cycle(s) detected:")
        for c in cycles:
            print(f"  {c}")

    if mismatches:
        print(f"\nVersion mismatches: {len(mismatches)}")
        for mm in mismatches:
            print(f"  {mm['plugin']} requires {mm['dependency']} {mm['constraint']}")
            print(f"    {mm['reason']}")
        print("\nUpdate outdated plugins:")
        for cmd in update_cmds:
            print(f"  {cmd}")

    if missing:
        print(f"\nMissing dependencies: {len(missing)}")
        if mp_cmds:
            print("\nFirst, add missing marketplaces:")
            for cmd in mp_cmds:
                print(f"  {cmd}")
        print("\nThen install missing plugins:")
        for cmd in install_cmds:
            print(f"  {cmd}")

    if not missing and not mismatches:
        print("\nAll dependencies satisfied.")


if __name__ == "__main__":
    main()
