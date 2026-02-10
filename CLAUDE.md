# Plugin Dependencies (`deps`)

Adds dependency resolution to Claude Code's plugin system.

## Convention

Plugins declare dependencies in a standalone `.claude-plugin/deps.json` file:

```json
{
  "other-plugin": {
    "marketplace": "marketplace-name",
    "source": "owner/repo",
    "version": ">=1.0.0"
  }
}
```

- `marketplace`: the local marketplace alias used with `/plugin install`
- `source`: GitHub `owner/repo` for adding the marketplace if not yet registered
- `version`: semver constraint — supports `=`, `>=`, `<=`, `>`, `<`, `!=`, `^`, `~`, and space-separated ranges

Legacy: the resolver also reads `dependencies` from `plugin.json` as a fallback.

## Version Constraints

| Syntax | Meaning | Example |
|--------|---------|---------|
| `>=1.2.3` | At least this version | `>=0.5.0` |
| `^1.2.3` | Compatible — same major | `^1.0.0` matches `1.x.x` |
| `~1.2.3` | Approximate — same minor | `~1.2.0` matches `1.2.x` |
| `>1.0.0 <2.0.0` | Range (AND) | Between 1 and 2 exclusive |
| `!=1.5.0` | Exclude a version | Not exactly 1.5.0 |
| `1.2.3` | Exact match | Only 1.2.3 |

Caret with major zero: `^0.2.3` means `>=0.2.3, <0.3.0` (minor is the compatibility boundary).

Pre-release versions sort below their release: `1.0.0-beta < 1.0.0`.

## Commands

| Command | Use when |
|---------|----------|
| `/deps:resolve` | After installing a plugin, to install its dependencies |
| `/deps:tree` | To view the full dependency graph |

## How It Works

The resolver reads `~/.claude/plugins/installed_plugins.json` to find all
installed plugins, reads each plugin's `deps.json` (or legacy `plugin.json`)
for dependency declarations, walks the tree, checks version constraints,
detects cycles, and reports what's missing or outdated along with the exact
commands to install or update them.
