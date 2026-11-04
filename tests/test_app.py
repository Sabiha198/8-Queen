import ast
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.algorithms import ALGORITHMS, solve
from backend.legacy import count_attacks, gen_all_succ

SOLUTION = [0, 4, 7, 5, 2, 6, 1, 3]

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', str(tmp_path / 'test.sqlite3'))
    with TestClient(main.app) as client:
        yield client


def test_original_functions_preserved():
    notebook = json.loads(next(Path('.').glob('*.ipynb')).read_text())
    original = {}
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            for node in ast.parse(''.join(cell['source'])).body:
                if isinstance(node, ast.FunctionDef) and node.name != 'test_algorithm':
                    original[node.name] = ast.dump(node)
    legacy = {node.name: ast.dump(node) for node in ast.parse(Path('backend/legacy.py').read_text()).body
              if isinstance(node, ast.FunctionDef)}
    assert original == legacy


def test_board_helpers():
    assert count_attacks(SOLUTION) == 0
    assert count_attacks([0] * 8) == 28
    successors = gen_all_succ(SOLUTION)
    assert len(set(successors)) == 56
    assert all(sum(a != b for a, b in zip(s, SOLUTION)) == 1 for s in successors)


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_initial_solution_and_trace(algorithm):
    result = solve(main.RunRequest(algorithm=algorithm, initial_state=SOLUTION))
    assert result['status'] == 'solved'
    assert result['solution'] == SOLUTION
    assert result['events'][-1]['conflicts'] == 0
    assert result['evaluations'] > 0


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_seeded_search_validity(algorithm):
    config = main.RunRequest(algorithm=algorithm, seed=12, max_attempts=100, trace_limit=10)
    first, second = solve(config), solve(config)
    assert first['best_state'] == second['best_state']
    assert first['evaluations'] == second['evaluations']
    assert count_attacks(first['best_state']) == first['conflicts']
    assert (first['status'] == 'solved') == (first['conflicts'] == 0)
    assert len(first['events']) <= 10
    assert first['events'][-1]['state'] == first['best_state']


def test_api_database_and_static(client):
    assert client.get('/').status_code == 200
    for path in ['app.js', 'style.css', 'vendor/bootstrap.min.css', 'vendor/chart.umd.js']:
        assert client.get('/static/' + path).status_code == 200
    assert client.get('/api/health').json()['status'] == 'ok'
    assert len(client.get('/api/algorithms').json()) == 7
    response = client.post('/api/runs', json={'algorithm':'rhc', 'initial_state':SOLUTION})
    assert response.status_code == 201
    run = response.json()
    assert run['solution'] == SOLUTION
    assert client.get(f"/api/runs/{run['id']}").json() == run
    history = client.get('/api/runs?algorithm=rhc').json()
    assert history['total'] == 1
    assert history['items'][0]['id'] == run['id']
    assert 'events' not in history['items'][0]
    with main.connect() as db:
        assert db.execute('SELECT count(*) FROM runs').fetchone()[0] == 1
    assert client.get('/api/runs/9999').status_code == 404
    assert client.get('/openapi.json').status_code == 200


@pytest.mark.parametrize('payload', [
 {'algorithm':'unknown'}, {'cooling_speed':0}, {'population_size':0},
 {'algorithm':'ga','population_size':3}, {'initial_state':[0,1]},
 {'initial_state':[8]*8}, {'max_attempts':0}, {'mutation_probability':2},
 {'timeout_seconds':100}, {'trace_limit':1}, {'extra':True},
])
def test_invalid_inputs(client, payload):
    assert client.post('/api/runs',json=payload).status_code == 422


def test_comparison_and_history_pagination(client):
    response = client.post('/api/comparisons', json={
        'algorithms':['hc','sa','ga'], 'trials':2,
        'settings':{'initial_state':SOLUTION,'max_attempts':5}})
    assert response.status_code == 200
    runs = response.json()['runs']
    assert len(runs) == 6
    assert all(run['status']=='solved' for run in runs)
    assert {run['parameters']['seed'] for run in runs} == {42,43}
    assert client.get('/api/runs?limit=2&offset=2').json()['total'] == 6
    assert len(client.get('/api/runs?limit=2&offset=2').json()['items']) == 2
    assert client.get('/api/runs?algorithm=ga').json()['total'] == 2
    assert client.post('/api/comparisons',json={'algorithms':[]}).status_code == 422
