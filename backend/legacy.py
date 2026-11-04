"""Original notebook functions, preserved for reference and compatibility."""

import random as rnd

from math import exp

def count_attacks(state):
    """Count the number of pairs of queens attacking each other in the given state."""
    ctr = 0
    for col1 in range(len(state)):
        for col2 in range(col1 + 1, len(state)):
            i1 = state[col1]
            i2 = state[col2]
            # Check if queens attack each other vertically, horizontally, or diagonally
            if i1 == i2 or col1 == col2 or (abs(i1 - i2) == abs(col1 - col2)): 
                ctr += 1
    return ctr

def gen_all_succ(state):
    """Generate all successor states by moving a single queen to a different row."""
    successors = []
    for column in range(len(state)):
        for row in range(len(state)):
            # Check if the queen in the current column is not already in the row
            if state[column] != row:
                new_state = list(state)
                new_state[column] = row
                successors.append(tuple(new_state))
    return successors

def hill_climb():
    """Perform hill climbing to find a state with minimal queen attacks."""
    # Initialize state randomly
    state = tuple([rnd.randint(0,7) for j in range(8)])
    state_attaks = count_attacks(state)

    while count_attacks(state) != 0:
        successors = gen_all_succ(state)
        # Calculate attacks for each successor
        costs = {s : count_attacks(s) for s in successors}
        min_val = min(costs.values())
                
        if min_val >= state_attaks:
            break
            
        min_states = [s for s in costs if costs[s] == min_val]        
        new_state = rnd.choice(min_states)
       
        state = new_state
        state_attaks = min_val
        
    return state, state_attaks

def random_hill_climbing(max_attempts=100):
    """Attempt to find a solution using hill climbing with random restarts."""
    for i in range(1, max_attempts):
        state = tuple([rnd.randint(0,7) for j in range(8)])
        state, counter = hill_climb()
        if counter == 0:
            return {state : 0}    
      
    return 'RHC Zero NOT founded'

def simulated_annealing(cooling_speed=1, max_attempts=10000):
    """Apply simulated annealing to find a state with minimal queen attacks."""
    # Initialize state randomly
    state = tuple([rnd.randint(0,7) for j in range(8)])
    state_attaks = count_attacks(state)
               
    if state_attaks == 0:
        return {state: 0}
    
    for attempt in range(1, max_attempts):
        temp = 1/(attempt*cooling_speed)
        if temp == 0:
            break
        new_state = rnd.choice(gen_all_succ(state))
        new_state_attaks = count_attacks(new_state)

        # Check if new state is a solution
        if new_state_attaks == 0:
            return {new_state: 0}

        # Determine whether to transition to the new state
        x = (new_state_attaks-state_attaks) / temp
        # Prevent out of range values
        if x < -500: x = -500
        criterion = exp(-x)
        
        if rnd.random() < criterion:
            state = new_state
            state_attaks = new_state_attaks

    return 'SA Zero NOT founded'

def beam_search(pop_size = 4, max_attempts = 5000):
    """Apply beam search to find a state with minimal queen attacks."""
    # Initialize population of states
    states = [tuple([rnd.randint(0,7) for j in range(8)]) for i in range(pop_size)]
    pop = {s : (28-count_attacks(s))/28 for s in states}
    
    for attempt in range(1, max_attempts):
        successors = []
        
        # Generate successors for each state in the population
        for state in pop:
            if pop[state] == 1:
                return {state: 1}
            successors.extend(gen_all_succ(state))     
        
        pop = [(s, (28-count_attacks(s))/28) for s in successors]
        
        rnd.shuffle(pop)
        '''Shuffle before ordering remove the bias that select always the best successors
        of the first queen that moves.
        E.g. if the second and forth queens generate 5 neighborurs with highest fit = 0.95
        and pop size is 5, the algorytm will always pick the first 5 states from the second queen.
        Shuffle it before ordereng prevent this'''
        
        # Prioritize successors with the least attacks    
        pop = sorted(pop, key=lambda st: st[1], reverse=True)
        pop = dict(pop[:pop_size])

    return 'LBS Fit NOT founded'

def stoc_beam_search(pop_size=5, max_attempts=5000):
    """Apply stochastic beam search to find a state with minimal queen attacks."""
    # Initialize population of states
    states = [tuple([rnd.randint(0,7) for j in range(8)]) for i in range(pop_size)]
    pop = {s : (28-count_attacks(s))/28 for s in states}
    
    for attempt in range(1, max_attempts):
        successors = []
        
        # Generate successors for each state in the population
        for state in pop:
            if pop[state] == 1:
                return {state: 1}
            successors.extend(gen_all_succ(state))     
        
        # Stochastically select states to be part of the next generation
        new_pop = [(s, (28-count_attacks(s))/28) for s in successors]
        pop_better_fit = [(p[0], p[1]) for p in new_pop if p[1] > min(pop.values())]

        if len(pop_better_fit) >= pop_size:
            pop = dict(rnd.choices(pop_better_fit, weights=[element[1] for element in pop_better_fit], k=pop_size))
        else:
            pop = dict(rnd.choices(new_pop, weights=[element[1] for element in new_pop], k=pop_size))

    return 'SLBS Fit NOT founded'

def selection(pop, pop_size):
    parents = rnd.choices(list(pop.items()), weights=pop.values(), k=pop_size)
    return [p[0] for p in parents]

def crossover(p1,p2):
    rnd_index = rnd.randint(0,7)
    child1 = p1[:rnd_index]+p2[rnd_index:]
    child2 = p2[:rnd_index]+p1[rnd_index:]
    return child1, child2

def mutation(state):
    rnd_index = rnd.randint(0,7)
    rnd_val = rnd.randint(0,7)
    new_state = list(state)
    '''While loop ensure the mutation exist. 
    E.g. if tuple (0,1,2,3,4,5,6,7) mutate at index 0 (so value is zero), if the mutation is the same value (zero)
    generate a new mutatiom, else return'''

    while new_state[rnd_index] == rnd_val:
        rnd_val = rnd.randint(0,7)
    new_state[rnd_index] = rnd_val
    
    return tuple(new_state)

def gen_alg(pop_size=100, mutation_prob=0.05, max_attempts=5000):
    """Apply a genetic algorithm to find a state with minimal queen attacks."""
    # Initialize population of states
    states = [tuple([rnd.randint(0,7) for j in range(8)]) for i in range(pop_size)]
    pop = {s : (28-count_attacks(s))/28 for s in states}

    for attempt in range(1, max_attempts): 
        for state in pop:
            if pop[state] == 1:
                return {state: 1}

        # Generate offspring from selected parents
        parents = selection(pop, pop_size)
        children = []
        
        '''The parents are selected sequentially from parents list moving from zero and pop_size/2
        E.g. pop size = 10, c in range(0, 5)
        first couple -> parents[0], parents[5]
        second couple -> parents[1], parents[6] ...
        This give pop_size/2 couple of children, for a total number of children = pop size'''


        for c in range(int(pop_size/2)):
            child1, child2 = crossover(parents[c], parents[c+int(pop_size/2)])

            if rnd.random() <= mutation_prob:
                child1 = mutation(child1) 
            children.append(child1)            
            if rnd.random() <= mutation_prob:
                child2 = mutation(child2)    
            children.append(child2)

        pop = {child : (28-count_attacks(child))/28 for child in children}
        
  
    return 'GA Fit 1 not founded'

def mutate(state):    
    rnd_index = rnd.randint(0,7)
    rnd_val = rnd.randint(0,7)
    new_state = list(state)
    while new_state[rnd_index] == rnd_val:
        rnd_val = rnd.randint(0,7)
    new_state[rnd_index] = rnd_val
    
    return tuple(new_state)

def mutate_MOD(state, max_pos_mutation_search):
    # Calculate the number of attacks in the current state.
    state_attaks = count_attacks(state)
    mutation_search = 0
    # Mutate the current state.
    new_state = mutate(state)
    
    # While the mutated state has more attacks than the original state and we haven't reached 
    # the maximum number of mutation attempts (max_pos_mutation_search), keep trying to mutate the state.
    while count_attacks(new_state) > state_attaks and mutation_search < max_pos_mutation_search:
        mutation_search += 1
        new_state = mutate(state)
        
    # Return the mutated state.
    return tuple(new_state)

def gen_alg_MOD(pop_size=1000, mutation_prob = 0.05, max_pos_mutation_search = 10,  max_attempts = 5000):   
    # Initialize the population with random states.
    states = [tuple([rnd.randint(0,7) for j in range(8)]) for i in range(pop_size)]
    # Calculate the fitness (how close each state is to the solution) of each state.
    pop = {s : (28-count_attacks(s))/28 for s in states}

    # Loop for a maximum of 'max_attempts' to find a solution.
    for attempt in range(1, max_attempts):    
        
        # Check each state in the population. If any state has a perfect fitness of 1 (i.e., 0 attacks), return it.
        for state in pop:
            if pop[state] == 1:
                return {state: 1}
            
        # Select parents for crossover from the population.
        parents = selection(pop, pop_size)
        children = []
            
        # Create children through crossover and possibly mutate them.
        for c in range(int(pop_size/2)):
            # Generate two children through crossover.
            child1, child2 = crossover(parents[c], parents[c+int(pop_size/2)])
            
            # With a probability of 'mutation_prob', mutate child1.
            if rnd.random() <= mutation_prob:
                child1 = mutate_MOD(child1, max_pos_mutation_search) 
            children.append(child1)  
            
            # With a probability of 'mutation_prob', mutate child2.          
            if rnd.random() <= mutation_prob:
                child2 = mutate_MOD(child2, max_pos_mutation_search)    
            children.append(child2)

        # Update the population with the new children and their fitnesses.
        pop = {s : (28-count_attacks(s))/28 for s in children}
    
    # If we've exhausted the maximum number of attempts without finding a solution, return a message indicating failure.
    return 'GAM - fit NOT founded'
