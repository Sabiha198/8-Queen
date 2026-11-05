"""FastAPI application and small SQLite persistence layer."""
import json
import logging
import os
import multiprocessing
import sqlite3
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .algorithms import ALGORITHMS, solve

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv('QUEENS_DB_PATH', str(ROOT / 'data' / 'queens.sqlite3'))


def connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, algorithm TEXT NOT NULL, created_at TEXT NOT NULL,
            parameters TEXT NOT NULL, result TEXT NOT NULL)''')


@asynccontextmanager
async def lifespan(app):
    initialize()
    app.state.pool = ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn"))
    app.state.slots = asyncio.Semaphore(2)
    yield
    app.state.pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title='Eight Queens Lab API', version='1.0.0', lifespan=lifespan,
              description='Real heuristic searches, recorded visualization traces, and SQLite history.')


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    algorithm: Literal['hc', 'rhc', 'sa', 'beam', 'stochastic', 'ga', 'gam'] = 'rhc'
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    max_attempts: int = Field(default=500, ge=1, le=5000)
    population_size: int = Field(default=30, ge=2, le=100)
    mutation_probability: float = Field(default=.1, ge=0, le=1)
    mutation_retries: int = Field(default=10, ge=0, le=30)
    cooling_speed: float = Field(default=1, gt=0, le=100)
    timeout_seconds: float = Field(default=5, ge=.1, le=15)
    trace_limit: int = Field(default=500, ge=2, le=1000)
    initial_state: list[int] | None = Field(default=None, min_length=8, max_length=8)

    @model_validator(mode='after')
    def validate_settings(self):
        if self.initial_state is not None and any(r < 0 or r > 7 for r in self.initial_state):
            raise ValueError('Each row must be between 0 and 7')
        if self.algorithm in ('ga', 'gam') and self.population_size % 2:
            raise ValueError('Genetic population size must be even')
        return self


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    algorithms: list[Literal['hc', 'rhc', 'sa', 'beam', 'stochastic', 'ga', 'gam']] = Field(min_length=1, max_length=7)
    trials: int = Field(default=3, ge=1, le=5)
    settings: RunRequest = Field(default_factory=RunRequest)

    @model_validator(mode='after')
    def validate_population(self):
        if any(a in ('ga', 'gam') for a in self.algorithms) and self.settings.population_size % 2:
            raise ValueError('Genetic population size must be even')
        return self


def save_run(config, result):
    created = datetime.now(timezone.utc).isoformat()
    parameters = config.model_dump()
    with connect() as db:
        cursor = db.execute('INSERT INTO runs(algorithm,created_at,parameters,result) VALUES(?,?,?,?)',
                            (config.algorithm, created, json.dumps(parameters), json.dumps(result)))
        run_id = cursor.lastrowid
    return {'id': run_id, 'algorithm': config.algorithm, 'created_at': created,
            'parameters': parameters, **result}


async def execute(config):
    async with app.state.slots:
        try:
            result = await asyncio.get_running_loop().run_in_executor(app.state.pool, solve, config)
            return save_run(config, result)
        except Exception as exc:
            logging.exception('Algorithm execution or persistence failed')
            raise HTTPException(500, 'Search could not complete; check server logs and database availability.') from exc


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/algorithms')
def algorithms():
    return [{'id': key, 'name': name, 'version': 'web-1'} for key, name in ALGORITHMS.items()]


@app.post('/api/runs', status_code=201)
async def create_run(config: RunRequest):
    return await execute(config)


@app.get('/api/runs')
def history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), algorithm: str | None = None):
    where, args = (' WHERE algorithm=?', [algorithm]) if algorithm else ('', [])
    with connect() as db:
        total = db.execute('SELECT COUNT(*) FROM runs' + where, args).fetchone()[0]
        rows = db.execute('SELECT * FROM runs' + where + ' ORDER BY id DESC LIMIT ? OFFSET ?',
                          args + [limit, offset]).fetchall()
    items = []
    for row in rows:
        result = json.loads(row['result'])
        result.pop('events', None)
        items.append({'id': row['id'], 'algorithm': row['algorithm'], 'created_at': row['created_at'],
                      'parameters': json.loads(row['parameters']), **result})
    return {'total': total, 'items': items}


@app.get('/api/runs/{run_id}')
def get_run(run_id: int):
    with connect() as db:
        row = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Execution not found')
    return {'id': row['id'], 'algorithm': row['algorithm'], 'created_at': row['created_at'],
            'parameters': json.loads(row['parameters']), **json.loads(row['result'])}


@app.post('/api/comparisons')
async def compare(request: ComparisonRequest):
    runs = []
    for algorithm in dict.fromkeys(request.algorithms):
        for trial in range(request.trials):
            settings = request.settings.model_dump()
            settings.update(algorithm=algorithm, seed=(request.settings.seed + trial) % 2**32)
            config = RunRequest.model_validate(settings)
            result = await execute(config)
            runs.append({k: v for k, v in result.items() if k != 'events'})
    return {'runs': runs, 'trials': request.trials}


app.mount('/static', StaticFiles(directory=ROOT / 'frontend'), name='static')


@app.get('/', include_in_schema=False)
def index():
    return FileResponse(ROOT / 'frontend' / 'index.html')
