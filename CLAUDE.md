# Plugin Dependencies (`deps`)

Adds dependency resolution to Claude Code's plugin system.

## Convention

Plugins can declare dependencies on other plugins by adding a `dependencies`
field to their `.claude-plugin/plugin.json`:

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

- `marketplace`: the local marketplace alias used with `/plugin install`
- `source`: GitHub `owner/repo` for adding the marketplace if not yet registered
- `version`: optional semver constraint (reserved for future use)

## Commands

| Command | Use when |
|---------|----------|
| `/deps:resolve` | After installing a plugin, to install its dependencies |
| `/deps:tree` | To view the full dependency graph |

## How It Works

The resolver reads `~/.claude/plugins/installed_plugins.json` to find all
installed plugins, reads each plugin's `plugin.json` for dependency
declarations, walks the tree, and reports what's missing along with the
exact commands to install them.
