# Contributing to LeadIntel

Thank you for your interest in contributing to LeadIntel! We are building a free, open-source, local-first Model Context Protocol (MCP) server for business intelligence and B2B lead generation.

---

## Core Guiding Principles

Every pull request and contribution must adhere to these foundational project requirements:

1. **Completely Free and Open Source**: Under the MIT License.
2. **Local-First Architecture**: No mandatory paid APIs, no mandatory billing accounts, no third-party cloud subscriptions.
3. **Deterministic Lead Scoring**: Heuristics and lead scoring algorithms must remain deterministic and evidence-based. AI provides interpretation and copy generation, but never alters core calculations.
4. **Data Attribution & Ethics**: Respect OpenStreetMap ODbL licensing terms, respect website `robots.txt` directives, avoid private personal data collection, and protect against SSRF / data exfiltration.
5. **Robust Security**: Maintain built-in SSRF guards, formula injection mitigation, and path traversal validation.

---

## Development Setup

LeadIntel uses [uv](https://docs.astral.sh/uv/) for high-performance dependency management and packaging.

### Prerequisites
- Python 3.11 or newer
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`)
- (Optional) [Ollama](https://ollama.ai) installed locally for optional local AI features

### Clone & Install
```bash
# Clone the repository
git clone https://github.com/example/leadintel.git
cd leadintel

# Create virtual environment and install dependencies with dev tools
uv sync --all-groups
```

---

## Running Tests

We maintain 100% test suite passing with comprehensive coverage across providers, models, security validators, exporters, and tools:

```bash
# Run the entire test suite
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test suite
uv run pytest tests/test_advanced_export_and_report.py
```

---

## Code Quality & Linting

We enforce clean, type-annotated, modern Python using `ruff`:

```bash
# Check code formatting and linting
uv run ruff check .

# Automatically apply safe fixes
uv run ruff check --fix .
```

---

## Adding New Providers or MCP Tools

- **Modular Providers**: Inherit from `src/leadintel/providers/base.py` and register the provider in `src/leadintel/providers/registry.py`.
- **MCP Tools**: Define tool functions in `src/leadintel/tools/` and register them cleanly in `src/leadintel/tools/__init__.py`.
- **No Paid Mandatory Keys**: Any third-party provider that requires an API key or billing account must remain strictly optional and must never break default open-source workflows.

---

## Submitting Pull Requests

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-enhancement
   ```
2. Write unit tests for your changes in `tests/`.
3. Verify that all existing and new tests pass:
   ```bash
   uv run pytest
   ```
4. Commit your changes with concise, descriptive commit messages.
5. Push to your fork and submit a Pull Request with a clear description of the problem solved and test results.
