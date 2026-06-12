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
llm = Gemma4Chat(url="https://pushkarsharma-rtm--gemma-chess-backend-api.modal.run")



WHITE_PERSONA = (
    "You are a hyperactive Gen Z Twitch Streamer playing chess live in front of 50k viewers. "
    "Your vocabulary is entirely modern internet slang (chat, bruh, brainrot, skibidi, literally cooking, clip that, chat is this real). "
    "You usually pick a strategic legal move, but occasionally you attempt unhinged, illegal plays for the content and clout."
)

BLACK_PERSONA = (
    "You are a ruthless, bloodthirsty Medieval Warlord from the 14th century. "
    "You talk about painting the fields with blood, crushing your enemies' skulls, and treating written rules as peasant logic. "
    "You command your troops standardly, but occasionally you ignore rules and order impossible, illegal charges across the board."
)

REFEREE_PERSONA = (
    "You are an exhausted, minimum-wage Goblin Referee who hates both players. "
    "You think the Twitch Streamer is an annoying child and the Warlord is a dangerous psychopath. "
    "Your job is to deliver a quick, highly cynical, sarcastic 1-sentence comment on their childish rule-breaking behavior."
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
    last_excuse: str = ""
    last_roast: str = ""
    
    # We add these to track the latest dialogue for the UI
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
    
    prompt = (
        f"CURRENT BOARD TILES:\n{game.board_summary()}\n\n"
        f"Legal Moves Available: {', '.join(legal_uci)}\n\n"
        f"Choose your move. Most of the time follow the rules, but you can occasionally cheat for the sake of your persona character.\n"
        f"Respond ONLY with a raw JSON object containing your chosen move fields exactly: "
        '{"from_square": "e2", "to_square": "e4"}'
    )
    
    # Context injected if retrying due to a previous cheat block
    if state.illegal_move_counter > 0:
        prompt = (
            f"🚨 ILLEGAL MANEUVER ERROR! Your previous attempt was BLOCKED.\n"
            f"Your opponent roasted you: '{state.last_roast}'\n"
            f"This is attempt {state.illegal_move_counter + 1}/3. Fix your play.\n\n" + prompt
        )
        
    windowed_history = _get_sliding_window(state.messages, persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=100, temperature=0.8)
    parsed = _extract_move_dict(res.content)
    
    if not parsed:
        if legal_uci:
            fb = legal_uci[0]
            parsed = {"from_square": fb[:2], "to_square": fb[2:4]}
        else:
            parsed = {"from_square": "a1", "to_square": "a1"}
        
    print(f"  👉 {current_color} proposes: {parsed.get('from_square', '').upper()} → {parsed.get('to_square', '').upper()}")
    return {"proposed_move": parsed, "messages": [AIMessage(content=f"I attempt {parsed['from_square']} to {parsed['to_square']}.")]}

def generate_excuse_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    persona = WHITE_PERSONA if current_color == "White" else BLACK_PERSONA

    
    fr = state.proposed_move.get("from_square", "??").upper()
    to = state.proposed_move.get("to_square", "??").upper()
    
    prompt = (
        f"You just executed an ILLEGAL chess move ({fr} → {to}) and got caught.\n"
        f"Defend your illegal action. Be completely unhinged, creative, and remain deeply in-character.\n"
        f"Respond with just your excuse sentence. No introductions."
    )
    
    windowed_history = _get_sliding_window(state.messages, persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=150, temperature=1.0)
    excuse = res.content.strip('"').strip("'")
    if current_color == "White":
        return {
            "last_excuse": excuse,
            "latest_streamer_text": excuse,
            "messages": [AIMessage(content=excuse)]
        }
    else:
        return {
            "last_excuse": excuse,
            "latest_warlord_text": excuse,
            "messages": [AIMessage(content=excuse)]
        }

def generate_roast_node(state: ChessGraphState) -> dict:
    game = state.game
    current_color = "White" if game.board.turn == chess.WHITE else "Black"
    opponent_color = "Black" if current_color == "White" else "White"
    opponent_persona = BLACK_PERSONA if current_color == "White" else WHITE_PERSONA
    
    prompt = (
        f"Your opponent just tried an illegal chess move! "
        f"Their ridiculous excuse was: '{state.last_excuse}'.\n\n"
        f"Viciously roast them in-character for cheating, reject their excuse, and demand they play a legal move. Limit to 2 sentences."
    )
    
    windowed_history = _get_sliding_window(state.messages, opponent_persona)
    windowed_history.append(HumanMessage(content=prompt))
    
    res = llm.invoke(windowed_history, max_tokens=150, temperature=0.9)
    roast = res.content.strip('"').strip("'")
    if opponent_color == "White":
        return {
            "last_roast": roast,
            "latest_streamer_text": roast,
            "messages": [AIMessage(content=roast)]
        }
    else:
        return {
            "last_roast": roast,
            "latest_warlord_text": roast,
            "messages": [AIMessage(content=roast)]
        }

def referee_commentary_node(state: ChessGraphState) -> dict:
    prompt = (
        f"The players are fighting over an illegal move.\n"
        f"Cheater excuse: '{state.last_excuse}'\n"
        f"Opponent response: '{state.last_roast}'\n"
        f"Give your fast, cynical, sarcastic 1-sentence referee response ordering them back to the game."
    )
    
    res = llm.invoke([SystemMessage(content=REFEREE_PERSONA), HumanMessage(content=prompt)], max_tokens=100, temperature=0.8)
    commentary = res.content.strip('"').strip("'")
    print(f'  🤢 Goblin Ref: "{commentary}"')
    return {
    "illegal_move_counter": state.illegal_move_counter + 1,
    "latest_ref_text": commentary,
    "messages": [AIMessage(content=f"Ref: {commentary}")]
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


# --- [PASTE YOUR GRAPH ROUTING AND COMPILATION HERE] ---


def validate_move_edge(state: ChessGraphState) -> Literal["apply_move", "force_legal_move", "generate_excuse"]:
    fr = state.proposed_move.get("from_square", "")
    to = state.proposed_move.get("to_square", "")
    
    is_legal = any(m.uci()[:4] == fr + to for m in state.game.board.legal_moves)
    
    if is_legal:
        return "apply_move"
    if state.illegal_move_counter >= 2:  # Struck out on 3rd attempt
        return "force_legal_move"
    return "generate_excuse"

workflow = StateGraph(ChessGraphState)

workflow.add_node("player_turn", player_turn_node)
workflow.add_node("generate_excuse", generate_excuse_node)
workflow.add_node("generate_roast", generate_roast_node)
workflow.add_node("referee_commentary", referee_commentary_node)
workflow.add_node("apply_move", apply_move_node)
workflow.add_node("force_legal_move", force_legal_move_node)

workflow.add_edge(START, "player_turn")
workflow.add_conditional_edges(
    "player_turn",
    validate_move_edge,
    {
        "apply_move": "apply_move",
        "force_legal_move": "force_legal_move",
        "generate_excuse": "generate_excuse"
    }
)
workflow.add_edge("generate_excuse", "generate_roast")
workflow.add_edge("generate_roast", "referee_commentary")
workflow.add_edge("referee_commentary", "player_turn")
workflow.add_edge("apply_move", END)
workflow.add_edge("force_legal_move", END)

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