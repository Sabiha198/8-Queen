"""Instrumented versions of the notebook searches; boards contain row per column."""
import random
from time import perf_counter
from math import exp
from .legacy import count_attacks, gen_all_succ

ALGORITHMS = {
    'hc': 'Hill climbing', 'rhc': 'Random-restart hill climbing',
    'sa': 'Simulated annealing', 'beam': 'Local beam search',
    'stochastic': 'Stochastic beam search', 'ga': 'Genetic algorithm',
    'gam': 'Modified genetic algorithm',
}


def solve(config):
    rng = random.Random(config.seed)
    started = perf_counter()
    evaluations = iterations = restarts = 0
    events = []
    best, best_cost = None, 29
    timed_out = False

    def cost(board):
        nonlocal evaluations, best, best_cost
        evaluations += 1
        value = count_attacks(board)
        if value < best_cost:
            best, best_cost = tuple(board), value
        return value

    def record(board, phase, **details):
        # Bounded trace: search continues when storage budget is reached.
        if len(events) < config.trace_limit:
            events.append({'step': iterations, 'state': list(board),
                           'conflicts': count_attacks(board), 'phase': phase, **details})

    def expired():
        nonlocal timed_out
        timed_out = perf_counter() - started >= config.timeout_seconds
        return timed_out

    def random_board():
        return tuple(rng.randrange(8) for _ in range(8))

    state = tuple(config.initial_state) if config.initial_state is not None else random_board()
    current = cost(state)
    record(state, 'Initial board')
    algorithm = config.algorithm
    if algorithm in ('hc', 'rhc'):
        for _ in range(config.max_attempts):
            if current == 0 or expired():
                break
            iterations += 1
            neighbors = gen_all_succ(state)
            scores = [cost(s) for s in neighbors]
            minimum = min(scores)
            if minimum >= current:
                if algorithm == 'hc':
                    break
                restarts += 1
                state = random_board()
                current = cost(state)
                record(state, 'Random restart', restart=restarts)
            else:
                state = rng.choice([s for s, score in zip(neighbors, scores) if score == minimum])
                current = minimum
                record(state, 'Improving move')
    elif algorithm == 'sa':
        for iteration in range(1, config.max_attempts + 1):
            if current == 0 or expired():
                break
            iterations += 1
            temperature = 1 / (iteration * config.cooling_speed)
            candidate = rng.choice(gen_all_succ(state))
            score = cost(candidate)
            accepted = score <= current or rng.random() < exp(-(score - current) / temperature)
            if accepted:
                state, current = candidate, score
            record(state, 'Annealing proposal', temperature=temperature, accepted=accepted,
                   candidate=list(candidate))
    else:
        population = [state] + [random_board() for _ in range(config.population_size - 1)]
        # Preserve the notebook's unique-board population representation.
        pop = {s: (28 - cost(s)) / 28 for s in population}

        def select(items, weights, size):
            return rng.choices(items, weights=weights if sum(weights) else None, k=size)

        def mutate(board):
            column = rng.randrange(8)
            row = rng.choice([r for r in range(8) if r != board[column]])
            return board[:column] + (row,) + board[column + 1:]

        for _ in range(config.max_attempts):
            if best_cost == 0 or expired():
                break
            iterations += 1
            if algorithm in ('beam', 'stochastic'):
                successors = [s for board in pop for s in gen_all_succ(board)]
                scored = [(s, (28 - cost(s)) / 28) for s in successors]
                if algorithm == 'beam':
                    rng.shuffle(scored)
                    scored.sort(key=lambda item: item[1], reverse=True)
                    pop = dict(scored[:config.population_size])
                else:
                    better = [item for item in scored if item[1] > min(pop.values())]
                    pool = better if len(better) >= config.population_size else scored
                    pop = dict(select(pool, [item[1] for item in pool], config.population_size))
            else:
                parents = select(list(pop), list(pop.values()), config.population_size)
                children = []
                half = config.population_size // 2
                for index in range(half):
                    p1, p2 = parents[index], parents[index + half]
                    cut = rng.randrange(8)
                    for child in (p1[:cut] + p2[cut:], p2[:cut] + p1[cut:]):
                        if rng.random() <= config.mutation_probability:
                            candidate = mutate(child)
                            if algorithm == 'gam':
                                original_cost = cost(child)
                                for retry in range(config.mutation_retries):
                                    if cost(candidate) <= original_cost:
                                        break
                                    candidate = mutate(child)
                            child = candidate
                        children.append(child)
                pop = {s: (28 - cost(s)) / 28 for s in children}
            representative = max(pop, key=pop.get)
            record(representative, 'Population generation', population_size=len(pop),
                   population=[list(s) for s in list(pop)[:12]])
        state, current = best, best_cost
    # Independently validate a discovered goal, including final-generation goals.
    success = best_cost == 0 and count_attacks(best) == 0
    final = best
    final_event = {'step': iterations, 'state': list(final), 'conflicts': best_cost,
                   'phase': 'Solution' if success else 'Best board'}
    truncated = len(events) >= config.trace_limit
    if truncated:
        events[-1] = final_event
    else:
        events.append(final_event)
    return {'algorithm_version': 'web-1', 'status': 'solved' if success else ('timeout' if timed_out else 'unsolved'),
            'solution': list(final) if success else None, 'best_state': list(final),
            'conflicts': best_cost, 'runtime_ms': (perf_counter() - started) * 1000,
            'evaluations': evaluations, 'iterations': iterations, 'restarts': restarts,
            'events': events, 'trace_truncated': truncated,
            'termination_reason': 'zero_conflicts' if success else ('time_limit' if timed_out else 'search_stopped')}
