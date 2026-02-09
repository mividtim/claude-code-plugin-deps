# claude-code-plugin-deps

Dependency resolution for [Claude Code](https://claude.ai/claude-code) plugins.

Claude Code's plugin system lets you install plugins from marketplaces, but doesn't resolve dependencies between them. This plugin adds that missing piece — scan installed plugins for dependency declarations, walk the tree, and install what's missing.

## Install

Add the marketplace and install:

```shell
/plugin marketplace add mividtim/claude-code-plugins
/plugin install deps@mividtim
```

## Usage

After installing a plugin that declares dependencies:

```shell
/deps:resolve
```

This scans all installed plugins, finds missing dependencies, and installs them. Run it again after installation to catch transitive dependencies.

To view the full dependency graph:

```shell
/deps:tree
```

## Declaring Dependencies

Plugin authors: add a `dependencies` field to your `.claude-plugin/plugin.json`:

```json
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
```

| Field | Required | Description |
|-------|----------|-------------|
| `marketplace` | Yes | Local marketplace alias for `/plugin install name@marketplace` |
| `source` | No | GitHub `owner/repo` — used to add the marketplace if not yet registered |
| `version` | No | Semver constraint (see below) |

### Version Constraints

| Syntax | Meaning |
|--------|---------|
| `>=1.2.3` | At least this version |
| `^1.2.3` | Compatible — same major (`^1.0.0` matches any `1.x.x`) |
| `~1.2.3` | Approximate — same minor (`~1.2.0` matches any `1.2.x`) |
| `>1.0.0 <2.0.0` | Range — space-separated constraints are AND'd |
| `!=1.5.0` | Exclude a specific version |
| `1.2.3` | Exact match |

Caret with major zero: `^0.2.3` means `>=0.2.3, <0.3.0`.

Pre-release versions (`1.0.0-beta`) sort below their release (`1.0.0`).

### Shorthand

If the dependency only needs a marketplace name:

```json
{
  "dependencies": {
    "other-plugin": "marketplace-name"
  }
}
```

## Example

The [claude-code-agency](https://github.com/mividtim/claude-code-agency) plugin declares a dependency on [event-listeners](https://github.com/mividtim/claude-code-event-listeners):

```json
{
  "name": "agency",
  "version": "1.0.0",
  "dependencies": {
    "deps": {
      "marketplace": "mividtim",
      "source": "mividtim/claude-code-plugins",
      "version": ">=0.1.0"
    },
    "el": {
      "marketplace": "mividtim",
      "source": "mividtim/claude-code-plugins",
      "version": "^0.5.0"
    }
  }
}
```

Running `/deps:resolve` after installing `agency` will detect that `el` is missing and provide the commands to install it.

## How It Works

1. Reads `~/.claude/plugins/installed_plugins.json` to find all installed plugins
2. Reads each plugin's `.claude-plugin/plugin.json` for `dependencies`
3. Walks the dependency tree with cycle detection
4. Checks installed versions against semver constraints
5. Reports missing plugins with exact install commands
6. Reports outdated plugins with update commands
7. Repeat until all dependencies are satisfied

## Related

- [claude-code-event-listeners](https://github.com/mividtim/claude-code-event-listeners) — Background event listeners for Claude Code
- [claude-code-agency](https://github.com/mividtim/claude-code-agency) — Persistent agent patterns for Claude Code
