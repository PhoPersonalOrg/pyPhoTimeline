# Development Container Configuration

This directory contains the configuration for GitHub Codespaces and dev container environments for the pyPhoTimeline project.

## Files

- **devcontainer.json**: VS Code dev container configuration to set up the Codespaces environment automatically.
- **devcontainer-setup.sh**: Initialization script that installs UV, dependencies, and sets up the Python environment with fallback strategy.

## How It Works

### Local Development

The `.devcontainer/` configuration enables **one-click setup** in GitHub Codespaces:

1. Create a new Codespace from the green "Code" button in GitHub
2. The container automatically:
   - Installs UV package manager
   - Installs `uv-deps-switcher` tool
   - Attempts dev mode (local sibling repos) with fallback to release mode
   - Syncs all dependencies
   - Sets up Python interpreters and VS Code extensions

### Automatic vs Manual Setup

| Scenario | Command |
|----------|---------|
| **GitHub Codespaces** | Automatic (devcontainer runs on create) |
| **Local dev container** (VS Code) | `Dev Containers: Rebuild and Reopen in Container` |
| **Manual setup** (existing CMD, Docker Desktop, etc.) | Run `.devcontainer/devcontainer-setup.sh` directly |

### Dependency Switching Strategy

The setup script implements a **fallback strategy**:

1. **Attempts dev mode first**: Uses local sibling repos at `../pyPhoCoreHelpers`, `../PhoPyLSLhelper`, `../PhoPyMNEHelper`
2. **Falls back to release mode**: If siblings aren't found, installs from GitHub instead
3. **Both modes sync fully**: Runs `uv sync --all-extras` regardless

This makes the environment **deterministic** whether in Codespaces (no siblings) or local dev (siblings present).

### VS Code Integration

The devcontainer.json automatically:
- Sets Python interpreter to `.venv/bin/python`
- Enables ruff linting
- Configures unittest discovery and debugging
- Installs recommended extensions (Python, Pylance, Ruff, debugpy)
- Sets up PYTHONPATH for proper module resolution

## Manual Execution

If you need to re-run setup without rebuilding the container:

```bash
# From workspace root
bash .devcontainer/devcontainer-setup.sh
```

## Troubleshooting

### UV Installation Issues
```bash
# Re-install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Sibling Repo Problems
If dev mode fails and you need local editable dependencies:
```bash
# Clone sibling repos to parent directory
cd ..
git clone https://github.com/CommanderPho/pyPhoCoreHelpers.git
git clone https://github.com/PhoPersonalOrg/phopylslhelper.git
git clone https://github.com/PhoPersonalOrg/PhoPyMNEHelper.git

# Switch back to dev mode
cd pyPhoTimeline
uv-deps-switcher dev
uv sync --all-extras
```

### Python Version Mismatch
Verify the environment uses Python 3.10:
```bash
python --version  # Should show 3.10.x
```

If using a different version, modify the `image` in `.devcontainer/devcontainer.json` or check `.python-version` in the workspace root.

## GitHub Actions CI/CD

Three workflows are configured in `.github/workflows/`:

- **test.yml**: Runs tests on Linux, macOS, Windows (Python 3.10)
- **lint.yml**: Code quality checks and import validation
- **dependency-check.yml**: Verifies `uv.lock` consistency and package builds

These run automatically on push to `master`, `main`, `develop` branches and on pull requests.

## For GitHub Agents (like Copilot)

The setup script is **agent-friendly**:
- Color-coded output (safe for terminal parsing)
- Explicit success/failure messages
- Bash error handling (`set -e`)
- Clear next-steps instructions
- Fallback mechanism prevents full setup failure

Agents can rely on:
- `.venv/bin/python` for executing code
- `.venv/bin/activate` for shell environment
- `uv` command being available on PATH
- Successful error messages guiding troubleshooting

## References

- [UV Package Manager](https://github.com/astral-sh/uv)
- [Dev Containers Specification](https://containers.dev)
- [GitHub Codespaces Documentation](https://docs.github.com/en/codespaces)
