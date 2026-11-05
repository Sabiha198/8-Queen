# Eight Queens · Search Lab

A full-stack, educational 8-Queens application built around the repository’s original heuristic-search notebook. Place queens, execute seven real search methods, replay their progress, compare measurements, and inspect persistent execution history.

## Features

- Responsive overview, interactive playground, results, comparison, and history views.
- Keyboard-accessible 8×8 board with one queen per column and conflict highlighting.
- Hill climbing, random-restart hill climbing, simulated annealing, local beam search, stochastic beam search, genetic algorithm, and modified genetic algorithm.
- Recorded search playback with play/pause, step, timeline, reset, and speed controls.
- Optional user-supplied starting board; reproducible random seeds.
- Runtime, conflict count, fitness evaluations, iteration and restart counts.
- Chart.js runtime and success-rate charts with a numerical comparison table.
- SQLite records containing UTC execution dates, parameters, boards, results, metrics, and traces; filtered, paginated history and replay.
- Validated FastAPI API, interactive Swagger documentation, and process-based search execution.
- Locally bundled Bootstrap 5.3.3 and Chart.js 4.4.8; no frontend build step or runtime CDN required.

## Stack and layout

```text
backend/main.py        FastAPI routes, request validation, SQLite persistence
backend/algorithms.py  Instrumented web search implementations
backend/legacy.py      Unchanged function definitions extracted from the notebook
frontend/index.html    All five application views
frontend/style.css     Responsive visual design
frontend/app.js        Board, playback, API calls, charts, and history
frontend/vendor/       Bootstrap and Chart.js assets
tests/test_app.py     Algorithm, API, persistence, and validation tests
```

The original notebook, `.Rhistory`, and `.gitattributes` remain intact. Pandas, Matplotlib, and Seaborn are only needed for the research notebook, not the web application.

## Installation and startup

Use Python 3.10 or newer. Run commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Windows activation: `.venv\Scripts\activate`.

Open **http://localhost:8000**. FastAPI serves both the frontend and backend; no separate frontend command is needed. For development, append `--reload` to the uvicorn command.

- Swagger API documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI schema: http://localhost:8000/openapi.json

SQLite is created automatically at `data/queens.sqlite3`. To select another persistent location, set `QUEENS_DB_PATH` before starting the server. Runtime databases and virtual environments are ignored by Git.

For the original research notebook, separately install `jupyter pandas matplotlib seaborn`, then open `Comparing different Search Algorithms on the 8 Queens Problem.ipynb`. Its full historical benchmark is expensive; do not run all cells casually.

## Using the application

1. Open Playground. Click a square to move the queen in that column, or randomize the board.
2. Choose an algorithm and settings. Leave “Start from this board” checked to use the displayed board; uncheck it for seeded random initialization.
3. Start search. The backend computes the run, saves it, and returns real recorded events.
4. Pause, step, scrub the timeline, or change playback speed. Results show the solution or best board.
5. Compare selected algorithms over 1–5 trials. The comparison uses the current playground settings and consecutive seeds. All trials appear in History.
6. Inspect any history entry to view its settings/result and replay its trace.

The overview’s board is an illustrative known solution; solver results and charts always come from backend execution.

## API

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/health` | Service liveness |
| GET | `/api/algorithms` | Seven algorithm identifiers, names, and version |
| POST | `/api/runs` | Execute and persist a run; HTTP 201 |
| GET | `/api/runs?limit=20&offset=0&algorithm=rhc` | Paginated history, optional algorithm filter |
| GET | `/api/runs/{id}` | Complete result including trace; 404 if absent |
| POST | `/api/comparisons` | Execute and persist selected algorithms over repeated trials |

Example:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"algorithm":"rhc","seed":42,"max_attempts":500}'
```

Algorithm IDs: `hc`, `rhc`, `sa`, `beam`, `stochastic`, `ga`, `gam`.

Run parameters and defaults:

| Field | Default | Limits / meaning |
|---|---|---|
| `seed` | 42 | Integer 0–4294967295 |
| `max_attempts` | 500 | 1–5000 search steps/generations |
| `population_size` | 30 | 2–100; even for genetic methods |
| `mutation_probability` | 0.1 | 0–1; genetic methods |
| `mutation_retries` | 10 | 0–30; modified GA |
| `cooling_speed` | 1 | Greater than 0, at most 100; annealing |
| `timeout_seconds` | 5 | 0.1–15; checked at iteration boundaries |
| `trace_limit` | 500 | 2–1000 stored events |
| `initial_state` | null | Exactly eight row values, each 0–7 |

A board is a row-per-column list. Zero conflicts means a valid solution. Responses include `id`, `algorithm`, `created_at`, `parameters`, `status`, `solution`, `best_state`, `conflicts`, `runtime_ms`, `evaluations`, `iterations`, `restarts`, `termination_reason`, `events`, and `trace_truncated`. Status is `solved`, `unsolved`, or `timeout`. Invalid requests return HTTP 422; missing history returns 404; execution/persistence errors return 500 and are logged.

Comparison request:

```json
{
  "algorithms": ["rhc", "sa", "beam"],
  "trials": 3,
  "settings": {"seed": 42, "max_attempts": 500, "population_size": 30}
}
```

Comparisons execute sequentially within the batch; up to two searches execute simultaneously across requests. A large batch may take minutes. Do not treat a small observed success rate sample as a guarantee. Evaluations count objective calls inside the search, including repeated calls; UI conflict rendering is excluded. Recorded-event overhead is included in runtime.

## Preservation and intentional fixes

`backend/legacy.py` preserves the original function ASTs exactly, verified automatically against the notebook. It remains importable with the original signatures and return conventions. `backend/algorithms.py` reuses the original attack counter and successor generator and retains the original search strategies, crossover, fitness, and mutation rules, adding instrumentation and consistent responses.

The web versions deliberately fix or extend behavior:

- Budgets include their last iteration; final-generation goals are recognized.
- Invalid settings are rejected, including zero cooling and odd genetic population sizes.
- Zero-total selection weights fall back to uniform selection.
- Each run uses a separate seeded random generator.
- Initial boards, best-so-far results, time budgets, and trace recording are supported.
- Restart hill climbing uses a shared search-step budget that includes restart steps; the original function retains its restart-count budget.
- Goals found while evaluating candidate boards are retained, even if not selected into the next population.
- Trace storage is bounded; if truncated, the final stored event is replaced by the true final result. There can be a jump in playback.

These extensions mean seeded web runs need not match legacy notebook runs. Dictionary population deduplication, possible stagnation, non-elitist genetic replacement, and the notebook’s reciprocal annealing schedule remain. No search is guaranteed to solve within a finite budget.

## Testing

```bash
python -m pytest -q
node --check frontend/app.js
```

Tests cover exact preservation of notebook functions; attack/successor correctness; all seven algorithms; seeded reproducibility; independently validated solutions; trace bounds; HTTP endpoints; static asset delivery; SQLite inserts/retrieval; history filtering/pagination; comparison execution; and invalid inputs. Tests use temporary databases and do not overwrite application history.

## Current boundaries

This is a complete local university-project application, not a multi-user hosted service. Search completes before playback begins; Pause affects playback, not the running server process. There is no live event streaming or cancellation endpoint. Population visualization displays the representative board and population size per generation rather than a full parent/crossover diagram. SQLite history belongs to this server and has no authentication. For public deployment, add authentication, job lifecycle/cancellation, request limits, and a persistent Python host with database backups. Use one Uvicorn worker for the documented two-process execution limit.

Third-party frontend assets retain their upstream MIT license notices. See `frontend/vendor/README.md`.
