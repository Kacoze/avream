# CLAUDE.md — AI Assistant Guide for AVream

AVream is a Linux application that turns an Android phone into a virtual webcam and microphone, appearing as standard V4L2/PulseAudio/PipeWire devices on the host system. It consists of a background daemon (`avreamd`), a GTK4/Libadwaita GUI (`avream-ui`), a CLI client (`avream`), and a small Rust privilege-escalation helper (`avream-helper`).

---

## Repository Layout

```
avream/
├── src/avreamd/          # Python daemon (asyncio + aiohttp REST API)
├── ui/src/avream_ui/     # Python GTK4/Libadwaita desktop application
├── helper/               # Rust binary for polkit privilege escalation
├── tests/
│   ├── unit/             # Fast unit tests (no I/O, no live processes)
│   └── integration/      # Live daemon socket tests
├── scripts/              # install, uninstall, doctor, build-deb, build-rpm…
├── docs/                 # mkdocs Markdown documentation source
├── debian/               # Debian/Ubuntu packaging
├── packaging/            # RPM, Flatpak, Snap, Arch, NixOS packaging
├── .github/workflows/    # CI/CD pipelines
├── Makefile              # Dev convenience targets
└── pyproject.toml        # Python project config, deps, tool settings
```

---

## Technology Stack

| Component | Language / Framework |
|-----------|----------------------|
| Daemon | Python 3.11+, asyncio, aiohttp |
| UI | Python 3.11+, GTK4, Libadwaita, pygobject |
| Privilege helper | Rust (serde, serde_json) |
| Build | setuptools + wheel |
| Linter | ruff |
| Type checker | mypy |
| Tests | pytest + unittest.IsolatedAsyncioTestCase |

---

## Development Environment

```bash
make venv          # Create .venv (Python 3.11+)
make install       # Editable install of daemon + UI
make unit          # Run unit tests
make integration   # Run integration tests (spins up live daemon)
make test          # unit + integration
make helper-check  # cargo check on the Rust helper
```

Activate the venv before running tools directly:

```bash
source .venv/bin/activate
ruff check src/ ui/        # Lint
mypy src/ ui/              # Type check
pytest tests/unit/         # Unit tests only
```

---

## Code Quality Rules

### Python
- **Ruff**: rules `E`, `F`, `I`; max line length **120**; target `python311`
- **mypy**: `python_version = "3.11"`, `warn_return_any = true`, `ignore_missing_imports = true`
- All new code must pass both tools without errors before committing.

### Rust (helper)
- Run `cargo check` (or `make helper-check`) after any changes in `helper/`.
- No clippy warnings should be introduced.

### General conventions
- Type annotations are expected on all function signatures in new code.
- Keep line length ≤ 120 characters.
- Never suppress mypy/ruff errors with inline comments without a clear justification.

---

## Architecture Overview

### Daemon (`src/avreamd/`)

The daemon follows a layered architecture:

```
api/          HTTP REST layer (aiohttp routes, middleware, schemas)
managers/     Orchestration logic (VideoManager, AudioManager, UpdateManager)
backends/     Feature implementations (AndroidVideoBackend)
core/         Shared infrastructure (DaemonStateStore, ProcessSupervisor)
integrations/ Thin wrappers for system tools (adb, scrcpy, v4l2loopback, pactl, pipewire)
domain/       Pure data models (VideoStartOptions, ReconnectPolicy, …)
bootstrap.py  Dependency injection — builds the DaemonDeps dataclass
app.py        AvreamDaemon orchestrator
main.py       Entry point, arg parsing, logging, signal handling
```

**Dependency injection**: `bootstrap.py` constructs a single `DaemonDeps` dataclass that holds every subsystem. Pass `DaemonDeps` (or individual fields) into constructors — do not import global singletons.

**State machine**: `core/state_store.py` enforces valid subsystem transitions:

```
STOPPED → STARTING → RUNNING → STOPPING → STOPPED
                         ↘ ERROR ↗
```

**Async-first**: the entire daemon is `asyncio`. Use `async/await` throughout. Blocking calls must be wrapped with `asyncio.to_thread` or run in an executor.

**API response envelope**: always use the helpers in `api/schemas.py`:

```python
success_envelope(data, request_id)       # {ok: true,  data: {...}}
error_envelope(request_id, code, msg, …) # {ok: false, error: {...}}
```

Never return a raw dict directly from a route handler.

**XDG compliance**: use `config.py` helpers (`get_runtime_dir()`, `get_config_dir()`, …). Never hard-code `~/.config` or `/tmp` paths.

### UI (`ui/src/avream_ui/`)

The UI communicates with the daemon over HTTP via `api_client.py`. Business logic is split into focused `window_behavior_*.py` modules; `window.py` is the GTK4 shell, and `window_state.py` tracks UI-side state.

### Rust helper (`helper/`)

A small binary that accepts JSON on stdin and performs privileged operations through polkit actions. It must remain minimal — add new actions only when genuinely required by the security model documented in `docs/SECURITY_DECISIONS.md`.

---

## Testing Conventions

### Structure

```
tests/
├── unit/daemon/      # One test file per daemon module
├── unit/ui/          # UI unit tests
├── unit/scripts/     # Script unit tests
├── integration/      # Live API contract tests
└── fixtures/         # Shared test helpers/fixtures
```

### Writing tests

- Use `unittest.IsolatedAsyncioTestCase` for async code.
- Mock all external processes and system calls in unit tests — no real ADB, scrcpy, or V4L2 calls.
- Name test files `test_<module_name>.py` matching the source module.
- Use pytest markers declared in `pyproject.toml`:
  - `@pytest.mark.unit` — fast, no I/O
  - `@pytest.mark.integration` — requires live daemon socket
  - `@pytest.mark.slow` — takes > 2 s

### Running specific tests

```bash
pytest tests/unit/daemon/test_state_store.py   # Single file
pytest -m unit                                  # All unit tests
pytest -m "not slow"                           # Skip slow tests
```

---

## API Contract

The REST API is documented in `docs/API_V1.md`. Key routes:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Daemon and subsystem status |
| POST | `/video/start` | Start video session |
| POST | `/video/stop` | Stop video session |
| POST | `/audio/start` | Start audio routing |
| POST | `/audio/stop` | Stop audio routing |
| GET | `/android/devices` | List ADB devices |
| GET | `/update/check` | Check for new release |
| POST | `/update/install` | Download and install update |

All responses follow the envelope format above. The daemon socket path comes from `config.get_socket_path()`.

---

## Adding New Features

1. **Domain model first**: add any new data structures to `domain/models.py`.
2. **Integration layer**: if a new system tool is needed, add a thin wrapper in `integrations/`.
3. **Manager/backend**: implement business logic in `managers/` or `backends/`.
4. **Wire it up**: register in `bootstrap.py` and expose via an `api/routes_*.py` module.
5. **Tests**: add corresponding `tests/unit/daemon/test_<module>.py`.
6. **Docs**: update `docs/API_V1.md` for new endpoints; update `docs/USER_GUIDE.md` for user-visible behaviour.

---

## Packaging Notes

| Format | Script / Config |
|--------|----------------|
| Debian/Ubuntu .deb | `scripts/build-deb.sh`, `debian/` |
| Split .deb packages | `scripts/build-deb-split.sh` |
| RPM (Fedora/openSUSE) | `scripts/build-rpm.sh`, `packaging/rpm/` |
| Arch AUR | `packaging/arch/` |
| Snap | `snap/` |
| Flatpak | `packaging/flatpak/` |
| NixOS | `flake.nix` |

Do not manually edit packaging configs without also updating the corresponding GitHub Actions workflow in `.github/workflows/`.

---

## Documentation

Source lives in `docs/` and is built with [mkdocs-material](https://squidfunk.github.io/mkdocs-material/):

```bash
pip install mkdocs mkdocs-material
mkdocs serve          # Live preview at http://localhost:8000
mkdocs build --strict # Build and validate (zero warnings)
```

Keep `docs/` in sync when changing user-visible behaviour, CLI flags, or the API contract.

---

## CI/CD Summary

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | Push / PR | Lint, type-check, unit tests, integration tests |
| `release.yml` | Git tag | Build all packages, create GitHub release |
| `nightly.yml` | Cron | Nightly artifact builds |
| `pages.yml` | Push to main | Deploy docs site |
| `snap.yml` | Push to main | Publish to Snap Store |
| `ppa.yml` | Push to main | Upload to Ubuntu PPA |

---

## Common Pitfalls

- **Do not block the event loop.** The daemon is fully async; any blocking call stalls every subsystem.
- **Do not hardcode paths.** Always use the helpers in `config.py`.
- **Do not bypass the state machine.** Set state through `DaemonStateStore` methods; never write state fields directly.
- **Do not skip the response envelope.** Raw dicts returned from routes break the CLI and UI clients.
- **Do not add polkit actions without updating `docs/SECURITY_DECISIONS.md`.** Security changes require explicit documentation.
- **Do not edit packaging configs in isolation.** CI workflows and packaging scripts must stay in sync.
