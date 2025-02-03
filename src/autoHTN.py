import pyhop
import json
import itertools

def check_enough (state, ID, item, num):
	if getattr(state,item)[ID] >= num: return []
	return False

def produce_enough (state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]

pyhop.declare_methods ('have_enough', check_enough, produce_enough)

def produce (state, ID, item):
	return [('produce_{}'.format(item), ID)]

pyhop.declare_methods ('produce', produce)

def make_method (name, rule):
	def method (state, ID):
		#tasks needed to complete our target reciepe
		tasks = []
		crafting_order = ['ingot', 'coal', 'ore', 'cobble', 'stick', 'plank','wood']

		#loop through each of our required items
		if 'Requires' in rule:
			#for each item we need, check if we have enough
			for item, num in rule['Requires'].items():
				tasks.append(('have_enough', ID, item, num))
		#check each of the consumed items in the order in which they are used in crafting
		if 'Consumes' in rule:
			for item in crafting_order:
				if item in rule['Consumes']:
					tasks.append(('have_enough', ID, item, rule['Consumes'][item]))

		tasks.append(('op_' + str(name).replace(" ", "_"), ID))

		return tasks
	
	#tag the function with the item it produces
	method.produces = next(iter(rule['Produces']))

	#tag function with the time needed to produce the item
	method.time = rule['Time']
	#give method new name
	method.__name__ = str(name).replace(" ", "_")

	return method

def declare_methods (data):
	# some recipes are faster than others for the same product even though they might require extra tools
	# sort the recipes so that faster recipes go first

	method_list = []

	#make methods for each recipe
	for recipe_name, recipe_data in data['Recipes'].items():
		method_list.append(make_method(recipe_name, recipe_data))

	#sort the methods by item and time
	method_list.sort(key=lambda method: (method.produces, method.time))

	#declare the methods
	for key, group in itertools.groupby(method_list, key=lambda recipe: recipe.produces):
		pyhop.declare_methods("produce_" + key, *group)
	# hint: call make_method, then declare the method to pyhop using pyhop.declare_methods('foo', m1, m2, ..., mk)	
				

def make_operator (rule):
	def operator (state, ID):
		#check if the state has the amount required to perform the operation
		if 'Requires' in rule:
			for item, num in rule['Requires'].items():
				if getattr(state, item)[ID] < num:
					return False
				

		#check if the state has enouhg of the consumed items
		if 'Consumes' in rule:
			for item, num in rule['Consumes'].items():
				if getattr(state, item)[ID] < num:
					return False
				
		#check if the state has enough time
		if state.time[ID] < rule['Time']:
			return False
		
		#remove the consumed item from the state
		if 'Consumes' in rule:
			for item, num in rule['Consumes'].items():
				getattr(state, item)[ID] -= num

		#add the produced item to the state
		for item, num in rule['Produces'].items():
			getattr(state, item)[ID] += num

		#subtract the time it took to produce the items
		state.time[ID] -= rule['Time']

		return state
	
	operator.produces = next(iter(rule['Produces']))
	operator.time = rule['Time']

	return operator

def declare_operators (data):
	operator_list = []

	for recipe_name, recipe_data in data['Recipes'].items():
		temp_operator = make_operator(recipe_data)
		
		temp_operator.__name__ = 'op_' + str(recipe_name).replace(" ", "_")
		operator_list.append(temp_operator)
	# hint: call make_operator, then declare the operator to pyhop using pyhop.declare_operators(o1, o2, ..., ok)
	pyhop.declare_operators(*operator_list)

def add_heuristic (data, ID):
	# prune search branch if heuristic() returns True
	# do not change parameters to heuristic(), but can add more heuristic functions with the same parameters: 
	# e.g. def heuristic2(...); pyhop.add_check(heuristic2)
	def heuristic (state, curr_task, tasks, plan, depth, calling_stack):
		# your code here
		if depth > 900:
			return True
		
		if curr_task[0] == 'produce':
			item_produced = curr_task[2]
			goals = data['Goal'].keys()

			if item_produced in data['Tools']:
				if curr_task in calling_stack:
					return True

			if item_produced in goals:
				return False

			if item_produced == 'iron_pickaxe':
				time_saved = {
					"coal": 1, 
					"ignot": 2, 
					"cobble": 1,
				}
				
				time_saved_total = 0
				for task in filter(lambda task: task[0] == 'have_enough'and task[2] in time_saved.keys(), tasks):
					time_saved_total += time_saved[task[2]] * task[3]

				if time_saved_total <= 18:
					return True
			
			if item_produced == 'stone_pickaxe':
				required_mining = sum(task[3] for task in filter(lambda task: task[0] == 'have_enough' and task[2] == 'cobble', tasks))
				if required_mining <= 7:
					return True

			if item_produced in ('wooden_axe', 'stone_axe'):
				required_wood = sum(task[3] for task in filter(lambda task: task[0] == 'have_enough' and task[2] in {'wood', 'planks'}, tasks))
				if required_wood <= 10 or (required_wood <= 12 and item_produced == 'stone_axe'):
					return True

			if item_produced == 'iron_axe':
				required_wood = sum(task[3] for task in filter(lambda tasl: task[0] == 'have_enough' and task[2] in {'wood', 'planks'}, tasks))

				if required_wood <= 20:
					return True

		max_repetitions = 10
		if len(calling_stack) > max_repetitions:
			last_tasks = calling_stack[-max_repetitions:]
			same_task_repeated = True
			for task in last_tasks:
				if task != curr_task:
					same_task_repeated = False
					break
			if same_task_repeated:
				return True

	pyhop.add_check(heuristic)


def set_up_state (data, ID, time=0):
	state = pyhop.State('state')
	state.time = {ID: time}

	for item in data['Items']:
		setattr(state, item, {ID: 0})

	for item in data['Tools']:
		setattr(state, item, {ID: 0})

	for item, num in data['Initial'].items():
		setattr(state, item, {ID: num})

	return state

def set_up_goals (data, ID):
	goals = []
	for item, num in data['Goal'].items():
		goals.append(('have_enough', ID, item, num))

	return goals

if __name__ == '__main__':
	rules_filename = 'crafting.json'

	with open(rules_filename) as f:
		data = json.load(f)

	state = set_up_state(data, 'agent', time=239) # allot time here
	goals = set_up_goals(data, 'agent')

	declare_operators(data)
	declare_methods(data)
	add_heuristic(data, 'agent')

	# pyhop.print_operators()
	# pyhop.print_methods()

	# Hint: verbose output can take a long time even if the solution is correct; 
	# try verbose=1 if it is taking too long
	pyhop.pyhop(state, goals, verbose=3)
	# pyhop.pyhop(state, [('have_enough', 'agent', 'cart', 1),('have_enough', 'agent', 'rail', 20)], verbose=3)
