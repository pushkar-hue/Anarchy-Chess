from frontend import play_next_turn

print("Testing play_next_turn...")
try:
    generator = play_next_turn(None)
    last_state = None
    for result in generator:
        board_html, streamer_chat, warlord_chat, ref_chat, state, status = result
        print(f"Status: {status}")
        last_state = state

    print("\n--- NEXT TURN ---")
    generator2 = play_next_turn(last_state)
    for result in generator2:
        board_html, streamer_chat, warlord_chat, ref_chat, state, status = result
        print(f"Status: {status}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}")
