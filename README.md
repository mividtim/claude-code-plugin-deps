# claude-code-plugin-deps

Dependency resolution for [Claude Code](https://claude.ai/claude-code) plugins.

Claude Code's plugin system lets you install plugins from marketplaces, but doesn't resolve dependencies between them. This plugin adds that missing piece — scan installed plugins for dependency declarations, walk the tree, and install what's missing.

## Install

Add this as a marketplace and install:

```shell
/plugin marketplace add mividtim/claude-code-plugin-deps
/plugin install deps@mividtim-claude-code-plugin-deps
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
| `version` | No | Semver constraint (reserved for future use) |

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
    "el": {
      "marketplace": "mividtim",
      "source": "mividtim/claude-code-event-listeners"
    }
  }
}
```

Running `/deps:resolve` after installing `agency` will detect that `el` is missing and provide the commands to install it.

## How It Works

1. Reads `~/.claude/plugins/installed_plugins.json` to find all installed plugins
2. Reads each plugin's `.claude-plugin/plugin.json` for `dependencies`
3. Walks the dependency tree
4. Reports missing plugins with exact install commands
5. Repeat until all dependencies are satisfied

## Related

- [claude-code-event-listeners](https://github.com/mividtim/claude-code-event-listeners) — Background event listeners for Claude Code
- [claude-code-agency](https://github.com/mividtim/claude-code-agency) — Persistent agent patterns for Claude Code
