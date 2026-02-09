---
description: Resolve and install missing plugin dependencies. Scans all installed plugins for dependency declarations and installs anything missing.
argument-hint: [--dry-run]
allowed-tools: Bash, Read
---

# Resolve Plugin Dependencies

Run the dependency resolver to scan all installed plugins:

```
Bash(command="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-deps.py resolve")
```

Read the output. If there are missing dependencies:

1. **Add missing marketplaces** — run any `/plugin marketplace add` commands listed
2. **Install missing plugins** — run each `/plugin install` command listed
3. **Re-run the resolver** to check for transitive dependencies that the newly installed plugins may declare

If `$ARGUMENTS` contains `--dry-run`, only report what would be installed without taking action.

Repeat until the resolver reports "All dependencies satisfied."
