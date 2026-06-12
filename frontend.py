import gradio as gr
import time
import chess.svg
import base64
import os
from backend import init_game, execute_turn_stream

# Attempt to load the background image as base64 to ensure it renders securely
bg_image_path = "room-castle_256339-5517.jpg"
bg_css = "background-color: #0f141e !important;" # Fallback
if os.path.exists(bg_image_path):
    try:
        with open(bg_image_path, "rb") as f:
            b64_bg = base64.b64encode(f.read()).decode("utf-8")
        bg_css = f"background-image: url('data:image/jpeg;base64,{b64_bg}') !important;"
    except Exception as e:
        print(f"Could not load background image: {e}")

# Modern, beautiful glassmorphism CSS
CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');

body, .gradio-container {{
    {bg_css}
    background-size: cover !important;
    background-position: center !important;
    background-attachment: fixed !important;
    font-family: 'Inter', sans-serif !important;
}}

/* Dark glass overlay for the main container */
#main-container {{
    background: rgba(15, 20, 30, 0.7); 
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    padding: 30px;
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 20px 50px rgba(0,0,0,0.6);
}}

h1 {{
    font-weight: 800;
    text-shadow: 0 4px 20px rgba(0,0,0,0.8);
    letter-spacing: 2px;
}}

/* Profile PFP CSS */
.profile-container {{
    display: flex;
    align-items: center;
    background: rgba(0, 0, 0, 0.4);
    border-radius: 16px;
    padding: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow: inset 0 2px 10px rgba(255,255,255,0.02), 0 4px 15px rgba(0,0,0,0.4);
    margin-bottom: 15px;
    transition: transform 0.3s ease;
}}
.profile-container:hover {{
    transform: translateY(-2px);
}}
.ref-profile {{
    justify-content: center;
    max-width: 350px;
    margin: 0 auto 15px auto;
}}
.pfp {{
    width: 65px;
    height: 65px;
    border-radius: 14px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 32px;
    margin-right: 15px;
    box-shadow: 0 8px 16px rgba(0,0,0,0.5);
    border: 2px solid rgba(255,255,255,0.1);
}}
.streamer-profile .pfp {{ background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%); }}
.warlord-profile .pfp {{ background: linear-gradient(135deg, #ff0844 0%, #ffb199 100%); }}
.ref-profile .pfp {{ background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); }}

.profile-info .name {{
    font-weight: 800;
    color: #ffffff;
    font-size: 18px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.8);
}}
.profile-info .role {{
    color: #a0aec0;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
}}

/* Glassmorphism Chat Boxes */
.glass-box {{
    background: rgba(10, 15, 25, 0.6) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 16px !important;
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.5) !important;
    overflow: hidden;
}}
.glass-box textarea {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 15px !important;
    line-height: 1.5 !important;
}}

.chat-box textarea {{ color: #00f2fe !important; text-shadow: 0 0 5px rgba(0,242,254,0.3); }}
.warlord-box textarea {{ color: #ff4b4b !important; text-shadow: 0 0 5px rgba(255,75,75,0.3); }}
.ref-box textarea {{ color: #f6d365 !important; font-style: italic; text-align: center; text-shadow: 0 0 5px rgba(246,211,101,0.3); }}

/* Chess Board Glow */
.board-container svg {{
    filter: drop-shadow(0 0 20px rgba(0,0,0,0.8));
    border-radius: 8px;
}}

/* Primary Button Styling */
button.primary {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
    box-shadow: 0 4px 15px rgba(118, 75, 162, 0.4) !important;
    color: white !important;
    font-weight: 800 !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    transition: all 0.3s ease !important;
}}
button.primary:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(118, 75, 162, 0.6) !important;
}}
"""

def render_board(board):
    """Converts the python-chess board into an SVG string for Gradio HTML."""
    svg_data = chess.svg.board(board, size=450)
    return f'<div class="board-container" style="display: flex; justify-content: center; padding: 10px;">{svg_data}</div>'

def typewriter_effect(text, current_text):
    """Yields text character by character to simulate a typewriter."""
    result = current_text + "\n" if current_text else ""
    for char in text:
        result += char
        time.sleep(0.015) # Adjust speed here
        yield result

def play_next_turn(state):
    """Handles the button click, streaming from the backend to the UI."""
    if state is None:
        state = init_game()

    board_html = render_board(state.game.board)
    streamer_chat = ""
    warlord_chat = ""
    ref_chat = ""
    status = "Thinking..."

    # If the game is over, don't execute any more turns.
    if state.game.board.is_game_over():
        status = f"🏁 GAME OVER: {state.game.board.result()}"
        yield board_html, streamer_chat, warlord_chat, ref_chat, state, status
        return

    # Stream the graph execution
    for node_name, updated_state in execute_turn_stream(state):
        state = updated_state
        board_html = render_board(state.game.board)
        
        # Determine who is talking based on the node and current turn
        current_turn = "White" if state.game.board.turn == chess.WHITE else "Black"
        
        if node_name == "player_turn":
            msg = f"[{current_turn}] Proposes move: {state.proposed_move.get('from_square', '??').upper()} to {state.proposed_move.get('to_square', '??').upper()}"
            status = "Move proposed..."
            if current_turn == "White":
                for f_text in typewriter_effect(msg, streamer_chat):
                    yield board_html, f_text, warlord_chat, ref_chat, state, status
                streamer_chat += msg + "\n"
            else:
                for f_text in typewriter_effect(msg, warlord_chat):
                    yield board_html, streamer_chat, f_text, ref_chat, state, status
                warlord_chat += msg + "\n"

        elif node_name == "generate_excuse":
            msg = f"[EXCUSE] {state.last_excuse}"
            status = "🚨 ILLEGAL MOVE DETECTED! Formulating excuse..."
            if current_turn == "White":
                for f_text in typewriter_effect(msg, streamer_chat):
                    yield board_html, f_text, warlord_chat, ref_chat, state, status
                streamer_chat += msg + "\n"
            else:
                for f_text in typewriter_effect(msg, warlord_chat):
                    yield board_html, streamer_chat, f_text, ref_chat, state, status
                warlord_chat += msg + "\n"

        elif node_name == "generate_roast":
            msg = f"[ROAST] {state.last_roast}"
            status = "Opponent is retaliating..."
            if current_turn == "White": # Black is roasting
                for f_text in typewriter_effect(msg, warlord_chat):
                    yield board_html, streamer_chat, f_text, ref_chat, state, status
                warlord_chat += msg + "\n"
            else: # White is roasting
                for f_text in typewriter_effect(msg, streamer_chat):
                    yield board_html, f_text, warlord_chat, ref_chat, state, status
                streamer_chat += msg + "\n"
                
        elif node_name == "referee_commentary":
            msg = f"[REF] {state.messages[-1].content}"
            status = "Referee steps in..."
            for f_text in typewriter_effect(msg, ref_chat):
                yield board_html, streamer_chat, warlord_chat, f_text, state, status
            ref_chat += msg + "\n"

    # Final yield for the completed turn
    if state.game.board.is_game_over():
        status = f"🏁 GAME OVER: {state.game.board.result()}"
    else:
        status = "Turn complete. Waiting for next player."
        
    yield board_html, streamer_chat, warlord_chat, ref_chat, state, status

def get_profile_html(emoji, name, role, pfp_class):
    return f'''
    <div class="profile-container {pfp_class}">
        <div class="pfp">{emoji}</div>
        <div class="profile-info">
            <div class="name">{name}</div>
            <div class="role">{role}</div>
        </div>
    </div>
    '''

# --- Gradio UI Layout ---
with gr.Blocks(css=CSS, theme=gr.themes.Monochrome()) as demo:
    state = gr.State(None)
    
    with gr.Column(elem_id="main-container"):
        gr.Markdown("<h1 style='text-align: center; color: white;'>♛ ANARCHY CHESS: THE GREAT HALL ♛</h1>")
        status_text = gr.Markdown("<h3 style='text-align: center; color: #a0aec0; font-weight: 400;'>Press 'Next Turn' to begin the chaos.</h3>")
        
        with gr.Row():
            # STREAMER UI (Top Left)
            with gr.Column(scale=1):
                gr.HTML(get_profile_html("🧑‍💻", "xX_ChessGod_Xx", "The Streamer", "streamer-profile"))
                streamer_box = gr.Textbox(label="Twitch Chat / Internal Monologue", lines=12, interactive=False, elem_classes=["glass-box", "chat-box"])
            
            # CHESSBOARD (Center)
            with gr.Column(scale=2):
                board_display = gr.HTML(render_board(chess.Board()))
                
                # We place the Referee right below the board so it's in the middle!
                gr.HTML("<div style='height: 20px;'></div>") # spacer
                gr.HTML(get_profile_html("👺", "Zog", "Goblin Referee", "ref-profile"))
                ref_box = gr.Textbox(label="", lines=2, interactive=False, show_label=False, elem_classes=["glass-box", "ref-box"])
                
                gr.HTML("<div style='height: 10px;'></div>") # spacer
                next_btn = gr.Button("▶ Play Next Turn", variant="primary", size="lg")
                
            # WARLORD UI (Top Right)
            with gr.Column(scale=1):
                gr.HTML(get_profile_html("⚔️", "Lord Malacor", "The Warlord", "warlord-profile"))
                warlord_box = gr.Textbox(label="Battle Cries", lines=12, interactive=False, elem_classes=["glass-box", "warlord-box"])
        
    # Wire up the button to our streaming function
    next_btn.click(
        fn=play_next_turn,
        inputs=[state],
        outputs=[board_display, streamer_box, warlord_box, ref_box, state, status_text]
    )

if __name__ == "__main__":
    demo.launch()