from backend import init_game, execute_turn_stream

state = init_game()
print("Starting turn 1")
try:
    for node, s in execute_turn_stream(state):
        print(f"Node: {node}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}")
