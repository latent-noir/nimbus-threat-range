#  Contributing

> *Every exploit patched makes the internet a little safer.*

Thanks for considering a contribution. Whether it's a new detection rule, a sharper visualization, or a bug fix — you're making this platform stronger.

## Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/cloud-simulator.git
cd cloud-simulator

# 2. Backend
cd core && pip install -r requirements.txt && python main.py

# 3. Frontend
cd web && npm install && npm run dev
```

## Workflow

1. **Fork** the repository
2. **Branch** — `git checkout -b feat/your-feature`
3. **Code** — follow the style guide below
4. **Test** — ensure existing tests pass
5. **Commit** — use conventional commits
6. **Push** — open a Pull Request

## Code Style

### Python
- PEP 8 · type hints on all signatures · docstrings on public APIs
- `async/await` for I/O · functions under 30 lines

### TypeScript
- Strict mode · interfaces for all data structures
- Functional components with hooks

## Commit Format

```
type(scope): description

feat(ids): add entropy-based anomaly detector
fix(api): correct WebSocket message validation
docs(readme): update architecture diagram
```

Types: `feat` · `fix` · `docs` · `style` · `refactor` · `test` · `chore`

## Areas We Need Help

-  New IDS detection rules and anomaly detectors
-  Additional attack vector simulations
-  Dashboard visualizations and UI enhancements
-  Expanded test coverage
-  Documentation and tutorials

## Code of Conduct

By contributing, you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

---

<p align="center"><sub>Build something that breaks things — so we can learn to defend them.</sub></p>
