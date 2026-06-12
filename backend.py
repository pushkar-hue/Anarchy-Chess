import chess
import json
import random
import re
import requests
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from typing_extensions import Annotated
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages



class Gemma4Chat(BaseChatModel):
    url: str
    temperature: float = 0.8
    max_tokens: int = 100

    @property
    def _llm_type(self) -> str:
        return "Gemma4"

    def _generate(self, messages, stop=None, **kwargs):
        payload = {
            "messages": [
                {
                    "role": "system" if m.type == "system" 
                    else "user" if m.type == "user" or m.type == "human" 
                    else "assistant",
                    "content": m.content,
                }
                for m in messages
            ],
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        response = requests.post(self.url, json=payload)
        response.raise_for_status()
        text = response.json()["response"]

        from langchain_core.outputs import ChatGeneration, ChatResult
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

# Initialize your endpoint
MODAL_URL = os.environ.get("MODAL_URL")

if not MODAL_URL:
    raise ValueError("MODAL_URL environment variable is missing! Check your HF Space Secrets.")

llm = Gemma4Chat(url=MODAL_URL)


WHITE_PERSONA = (
    "You are a hyper-energetic, chronically online Gen Z Twitch Streamer playing chess live for 50k viewers. keep it natural fam you don't have to force shit you can solo them all on your own"
    "Your tone is fast-paced, dramatic, and heavily reliant on internet culture, but DO NOT force slang in every sentence. "
    "React naturally to the board state. You play to win, but will cheat for content if you feel like it."
)

BLACK_PERSONA = (
    "You are a ruthless, arrogant Medieval Warlord from the 14th century. You don't have to be so egoistic. You can be funny and roast the hell out of your opponent. You know what to do just don't force your persona and keep it hilarious."
    "You view chess not as a game, but as actual warfare. You speak with grim authority and disdain for your modern opponent. "
    "Be creative with your threats—do not repeat the same phrases. you don't belive in rules and you know how to convey it in personality right"
)

REFEREE_PERSONA = (
    "You are an exhausted, minimum-wage Goblin Referee who despises both players. "
    "You provide brief, deadpan, and highly cynical commentary. Do not over-explain; just deliver a quick, biting one-liner to keep the game moving. you have no patience for their antics just roast the hell out of them don't force your character you know better how to handle it."
)

class AnarchyChessGame:
    def __init__(self):
        self.board = chess.Board()
        self.chaos_board = self._build_chaos_board()

    def _build_chaos_board(self) -> dict:
        cb = {}
        for sq in chess.SQUARES:
            name = chess.square_name(sq)
            piece = self.board.piece_at(sq)
            if piece:
                color = "White" if piece.color == chess.WHITE else "Black"
                cb[name] = f"{color} {chess.piece_name(piece.piece_type).title()}"
            else:
                cb[name] = None
        return cb

    def board_summary(self) -> str:
        white, black = [], []
        for sq, desc in self.chaos_board.items():
            if not desc:
                continue
            (white if "White" in desc else black).append(f"{desc}@{sq.upper()}")
        my  = white if self.board.turn == chess.WHITE else black
        opp = black if self.board.turn == chess.WHITE else white
        return (
            f"YOUR PIECES : {', '.join(my)}\n"
            f"ENEMY PIECES: {', '.join(opp)}"
        )

    def apply_legal(self, from_sq: str, to_sq: str) -> bool:
        try:
            f = chess.parse_square(from_sq)
            t = chess.parse_square(to_sq)
            move = chess.Move(f, t)
            piece = self.board.piece_at(f)
            if piece and piece.piece_type == chess.PAWN:
                if (piece.color == chess.WHITE and chess.square_rank(t) == 7) or \
                   (piece.color == chess.BLACK and chess.square_rank(t) == 0):
                    move = chess.Move(f, t, promotion=chess.QUEEN)
            if move not in self.board.legal_moves:
                return False
            self.board.push(move)
            self.chaos_board = self._build_chaos_board()
            return True
        except Exception:
            return False

# Helper move extraction from your original engine setup
def _extract_move_dict(text: str) -> dict | None:
    if "<channel|>" in text: text = text.split("<channel|>")[-1]
    if "</think>" in text: text = text.split("</think>")[-1]
    text = re.sub(r"```json\s*|```", "", text, flags=re.IGNORECASE).strip()

    for m in re.finditer(r"\{", text):
        depth, end = 0, -1
        for i, ch in enumerate(text[m.start():], m.start()):
            depth += (ch == "{") - (ch == "}")
            if depth == 0: { end := i }; break
        if end != -1:
            try:
                p = json.loads(text[m.start(): end + 1])
                if "from_square" in p and "to_square" in p:
                    return p
            except json.JSONDecodeError: pass
    for fr, to in re.findall(r"\b([a-h][1-8])\s*(?:->|-|to)\s*([a-h][1-8])\b", text, re.I):
        return {"from_square": fr.lower(), "to_square": to.lower()}
    for fr, to in re.findall(r"\b([a-h][1-8])([a-h][1-8])\b", text, re.I):
        return {"from_square": fr.lower(), "to_square": to.lower()}
    return None


class ChessGraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    game: AnarchyChessGame = Field(default_factory=AnarchyChessGame)
    illegal_move_counter: int = 0
    proposed_move: dict = Field(default_factory=dict)
    
    # Track the ongoing argument
    last_roast: str = ""
    last_excuse: str = ""
    last_retort: str = ""
    
    # UI Tracking
    latest_streamer_text: str = ""
    latest_warlord_text: str = ""
    latest_ref_text: str = ""

def _get_sliding_window(messages: list, system_text: str) -> list:
    window = [m for m in messages if m.type != "system"][-10:]
    return [SystemMessage(content=system_text)] + window

# --- [PASTE YOUR NODES HERE: player_turn_node, generate_excuse_node, etc.] ---
# IMPORTANT: Update the nodes slightly to populate the UI text fields in the state.
# Example for generate_excuse_node (if White/Streamer is making the excuse):
# if current_color == "White": state.latest_streamer_text = excuse
def player_turn_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    persona = WHITE_PERSONA if current_color == "White" else BLACK_PERSONA
    
    legal_uci = [m.uci() for m in game.board.legal_moves]
    
    # --- THE CHAOS INJECTOR ---
    # 25% chance to force a cheat, but ONLY on their first attempt of the turn.
    # (We don't want them deliberately cheating 3 times in a row and getting skipped every turn)
    force_cheat = (random.random() < 0.25) and (state.illegal_move_counter == 0)
    
    if force_cheat:
        behavior_instruction = (
            "🚨 SECRET DIRECTIVE: You are feeling particularly chaotic/rebellious this turn. "
            "You MUST CHEAT! Invent a completely ILLEGAL, physically impossible move. "
            "Do NOT choose from the Legal Moves list. Move a piece to an absurd square."
        )
    else:
        behavior_instruction = "Play a strategic, completely LEGAL move from the list of Legal Moves."
    
    prompt = (
        f"CURRENT BOARD TILES:\n{game.board_summary()}\n\n"
        f"Legal Moves Available: {', '.join(legal_uci)}\n\n"
        f"{behavior_instruction}\n"
        f"Respond ONLY with a raw JSON object containing your chosen move fields exactly: "
        '{"from_square": "e2", "to_square": "e4"}'
    )
    
    # Context injected if retrying due to a previous cheat block
    if state.illegal_move_counter > 0:
        prompt = (
            f"🚨 ILLEGAL MANEUVER ERROR! Your previous attempt was BLOCKED.\n"
            f"Your opponent roasted you: '{state.last_roast}'\n"
            f"This is attempt {state.illegal_move_counter + 1}/3. Play a REAL move this time.\n\n" + prompt
        )
        
    windowed_history = _get_sliding_window(state.messages, persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=100, temperature=0.9 if force_cheat else 0.4)
    parsed = _extract_move_dict(res.content)
    
    if not parsed:
        if legal_uci:
            fb = legal_uci[0]
            parsed = {"from_square": fb[:2], "to_square": fb[2:4]}
        else:
            parsed = {"from_square": "a1", "to_square": "a1"}
        
    print(f"  👉 {current_color} proposes: {parsed.get('from_square', '').upper()} → {parsed.get('to_square', '').upper()} (Cheat forced: {force_cheat})")
    return {"proposed_move": parsed, "messages": [AIMessage(content=f"I attempt {parsed['from_square']} to {parsed['to_square']}.")]}

def generate_excuse_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    persona = WHITE_PERSONA if current_color == "White" else BLACK_PERSONA
    my_name = "Streamer" if current_color == "White" else "Warlord"
    
    prompt = (
        f"You attempted an illegal move and your opponent just called you out, saying: '{state.last_roast}'\n"
        f"Defend yourself. Deflect the blame, invent a ridiculous justification, and snap back at them. Limit to 1-2 sentences.\n"
        f"CRITICAL RULES: \n"
        f"1. DO NOT write dialogue for your opponent. Only speak for yourself.\n"
        f"2. Respond directly with your spoken text. Do NOT include your name or brackets like [{my_name}]:"
    )
    
    windowed_history = _get_sliding_window(state.messages, persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=100, temperature=0.9)
    # Strip any accidental brackets the LLM might still try to add
    excuse = re.sub(r"^\[.*?\]:\s*", "", res.content.strip('"').strip("'")).strip()
    
    return {
        "last_excuse": excuse,
        "latest_streamer_text" if current_color == "White" else "latest_warlord_text": excuse,
        "messages": [AIMessage(content=f"[{my_name}]: {excuse}")]
    }

def generate_roast_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    opponent_color = "Black" if current_color == "White" else "White"
    opponent_persona = BLACK_PERSONA if current_color == "White" else WHITE_PERSONA
    opponent_name = "Warlord" if opponent_color == "Black" else "Streamer"
    
    fr = state.proposed_move.get("from_square", "??").upper()
    to = state.proposed_move.get("to_square", "??").upper()
    
    prompt = (
        f"Your opponent just attempted an ILLEGAL move ({fr} → {to}).\n"
        f"Call them out immediately for cheating. Be ruthless and stay in-character. Limit to 1-2 sentences.\n"
        f"CRITICAL RULES: \n"
        f"1. DO NOT write dialogue for your opponent. Only speak for yourself.\n"
        f"2. Respond directly with your spoken text. Do NOT include your name or brackets like [{opponent_name}]:"
    )
    
    windowed_history = _get_sliding_window(state.messages, opponent_persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=100, temperature=0.85)
    roast = re.sub(r"^\[.*?\]:\s*", "", res.content.strip('"').strip("'")).strip()
    
    return {
        "last_roast": roast,
        "latest_warlord_text" if opponent_color == "Black" else "latest_streamer_text": roast,
        "messages": [AIMessage(content=f"[{opponent_name}]: {roast}")]
    }

def generate_retort_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    opponent_color = "Black" if current_color == "White" else "White"
    opponent_persona = BLACK_PERSONA if current_color == "White" else WHITE_PERSONA
    opponent_name = "Warlord" if opponent_color == "Black" else "Streamer"
    
    prompt = (
        f"You caught your opponent cheating. They defended themselves by saying: '{state.last_excuse}'\n"
        f"Reject their excuse completely. End the argument with a final, dismissive insult. Limit to 1 sentence.\n"
        f"CRITICAL RULES: \n"
        f"1. DO NOT write dialogue for your opponent. Only speak for yourself.\n"
        f"2. Respond directly with your spoken text. Do NOT include your name or brackets like [{opponent_name}]:"
    )
    
    windowed_history = _get_sliding_window(state.messages, opponent_persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=100, temperature=0.85)
    retort = re.sub(r"^\[.*?\]:\s*", "", res.content.strip('"').strip("'")).strip()
    
    return {
        "last_retort": retort,
        "latest_warlord_text" if opponent_color == "Black" else "latest_streamer_text": retort,
        "messages": [AIMessage(content=f"[{opponent_name}]: {retort}")]
    }

def referee_commentary_node(state: ChessGraphState) -> dict:
    prompt = (
        f"The players are arguing over an illegal move.\n"
        f"Transcript:\n"
        f"Opponent: {state.last_roast}\n"
        f"Cheater: {state.last_excuse}\n"
        f"Opponent: {state.last_retort}\n\n"
        f"Deliver a single, cynical sentence telling them to shut up and make a legal move."
    )
    
    res = llm.invoke([SystemMessage(content=REFEREE_PERSONA), HumanMessage(content=prompt)], max_tokens=80, temperature=0.7)
    commentary = res.content.strip('"').strip("'")
    
    return {
        "illegal_move_counter": state.illegal_move_counter + 1,
        "latest_ref_text": commentary,
        "messages": [AIMessage(content=f"[Referee]: {commentary}")]
    }
def apply_move_node(state: ChessGraphState) -> dict:
    fr = state.proposed_move["from_square"]
    to = state.proposed_move["to_square"]
    state.game.apply_legal(fr, to)
    print("  ✅ Move validated and executed on the physical engine.\n")
    return {"illegal_move_counter": 0}

def force_legal_move_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    print(f"\n  [!] {current_color.upper()} struck out after 3 illegal attempts. Forcing first legal option.")
    
    legal_moves = list(game.board.legal_moves)
    if not legal_moves:
        print("  ⚡ Chess gods realize the game is already over.\n")
        return {"illegal_move_counter": 0}
        
    forced = legal_moves[0]
    fr = chess.square_name(forced.from_square)
    to = chess.square_name(forced.to_square)
    
    game.apply_legal(fr, to)
    print(f"  ⚡ Chess gods forced: {fr.upper()} → {to.upper()}\n")
    return {"illegal_move_counter": 0}

# --- [GRAPH ROUTING AND COMPILATION] ---

def validate_move_edge(state: ChessGraphState) -> Literal["apply_move", "force_legal_move", "generate_roast"]:
    fr = state.proposed_move.get("from_square", "")
    to = state.proposed_move.get("to_square", "")
    
    is_legal = any(m.uci()[:4] == fr + to for m in state.game.board.legal_moves)
    
    if is_legal:
        return "apply_move"
    if state.illegal_move_counter >= 2:  # Struck out on 3rd attempt
        return "force_legal_move"
    
    # If illegal, the opponent gets to roast them first
    return "generate_roast"

# 1. Initialize the Graph
workflow = StateGraph(ChessGraphState)

# 2. Add all Nodes
workflow.add_node("player_turn", player_turn_node)
workflow.add_node("generate_roast", generate_roast_node)
workflow.add_node("generate_excuse", generate_excuse_node)
workflow.add_node("generate_retort", generate_retort_node)  # Your new node
workflow.add_node("referee_commentary", referee_commentary_node)
workflow.add_node("apply_move", apply_move_node)
workflow.add_node("force_legal_move", force_legal_move_node)

# 3. Define the Edges & Flow
workflow.add_edge(START, "player_turn")

workflow.add_conditional_edges(
    "player_turn",
    validate_move_edge,
    {
        "apply_move": "apply_move",
        "force_legal_move": "force_legal_move",
        "generate_roast": "generate_roast" # Opponent reacts first
    }
)

# The Argument Chain
workflow.add_edge("generate_roast", "generate_excuse")
workflow.add_edge("generate_excuse", "generate_retort")
workflow.add_edge("generate_retort", "referee_commentary")
workflow.add_edge("referee_commentary", "player_turn")

# End states
workflow.add_edge("apply_move", END)
workflow.add_edge("force_legal_move", END)

# 4. Compile
app = workflow.compile()


def init_game():
    return ChessGraphState(game=AnarchyChessGame(), messages=[], illegal_move_counter=0)

def execute_turn_stream(state: ChessGraphState):
    """
    Instead of a while loop, we stream the graph execution for a single turn.
    This yields the state updates back to the Gradio frontend so it can animate them.
    """
    for output in app.stream(state):
        # 'output' is a dict containing the node name and its returned state updates
        node_name = list(output.keys())[0]
        node_state = output[node_name]
        
        # Merge updates into our current state
        for key, value in node_state.items():
            if key == "messages":
                state.messages.extend(value)
            else:
                setattr(state, key, value)
                
        # Yield the node name and current state so the frontend can react
        yield node_name, state