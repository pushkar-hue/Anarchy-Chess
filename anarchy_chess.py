import chess
import json
import requests
import re
import random
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────
#  Models
# ─────────────────────────────────────────────

class MoveResponse(BaseModel):
    explanation: str = Field(default="...")
    from_square: str
    to_square: str

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────

# Updated to match the new Modal app name
# Note: Ensure this URL exactly matches the output from `modal deploy`
URL = "https://pushkarsharma-rtm--gemma-chess-backend-api.modal.run"

WHITE_PERSONA = (
    "You are an Astrophysicist who views the chess board as a volatile quantum field. "
    "You usually play standard, strategic chess, but occasionally you use quantum tunneling "
    "or bend spacetime to execute illegal moves."
)
BLACK_PERSONA = (
    "You are a ruthless, bloodthirsty Medieval Warlord. "
    "You usually command your troops with standard military strategy, but occasionally "
    "you ignore the rules entirely and order impossible, illegal charges across the board."
)

# ─────────────────────────────────────────────
#  Game State
# ─────────────────────────────────────────────

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

    def apply_illegal(self, from_sq: str, to_sq: str) -> bool:
        """Applies the illegal move. Summoning mechanics activated if the tile is a ghost square!"""
        try:
            f = chess.parse_square(from_sq)
            t = chess.parse_square(to_sq)
            piece = self.board.piece_at(f)
            
            if not piece:
                # 🌀 PIECE SUMMONING MECHANIC
                chaotic_options = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
                chosen_type = random.choice(chaotic_options)
                piece = chess.Piece(chosen_type, self.board.turn)
                print(f"  ✨ ANARCHY! Manifested a brand new {chess.piece_name(chosen_type).upper()} out of cosmic dust!")
            else:
                self.board.remove_piece_at(f)
                
            self.board.set_piece_at(t, piece)
            self.board.turn = not self.board.turn
            self.board.clear_stack()
            self.board.castling_rights = chess.BB_EMPTY
            self.chaos_board = self._build_chaos_board()
            return True
        except Exception as e:
            print(f"  💥 [Chaos Error] Quantum state rejected: {e}")
            return False

# ─────────────────────────────────────────────
#  API helpers
# ─────────────────────────────────────────────

def _post(payload: dict) -> str:
    try:
        r = requests.post(URL, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data.get("response", str(data))
    except Exception as e:
        print(f"  [API error] {e}")
        return ""

def _strip_think_tags(text: str) -> str:
    """Safely removes legacy <think> blocks and Gemma 4 thought channels."""
    # Gemma 4 uses <|channel>thought\n ... <channel|> internally
    if "<channel|>" in text:
        text = text.split("<channel|>")[-1]
    elif "<|channel>" in text:
        text = re.sub(r"<\|channel>.*", "", text, flags=re.DOTALL)
        
    # Fallback for older reasoning blocks
    if "</think>" in text:
        text = text.split("</think>")[-1]
    elif "<think>" in text:
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
        
    # Gemma models often wrap JSON in markdown; strip it out
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text)
    
    return text.strip()

def _extract_move(text: str) -> dict | None:
    cleaned = _strip_think_tags(text)

    # 1 – proper JSON blocks
    for m in re.finditer(r"\{", cleaned):
        depth, end = 0, -1
        for i, ch in enumerate(cleaned[m.start():], m.start()):
            depth += (ch == "{") - (ch == "}")
            if depth == 0:
                end = i
                break
        if end == -1:
            continue
        try:
            p = json.loads(cleaned[m.start(): end + 1])
            if "from_square" in p and "to_square" in p:
                return p
        except json.JSONDecodeError:
            pass

    # 2 – arrow/to patterns: e2->e4, e2 to e4, e2-e4
    for fr, to in re.findall(r"\b([a-h][1-8])\s*(?:->|-|to)\s*([a-h][1-8])\b", cleaned, re.I):
        return {"from_square": fr.lower(), "to_square": to.lower()}

    # 3 – bare UCI: e2e4
    for fr, to in re.findall(r"\b([a-h][1-8])([a-h][1-8])\b", cleaned, re.I):
        return {"from_square": fr.lower(), "to_square": to.lower()}

    # 4 – loose field regex
    fr = re.search(r'"from_square"\s*:\s*"([a-h][1-8])"', cleaned, re.I)
    to = re.search(r'"to_square"\s*:\s*"([a-h][1-8])"', cleaned, re.I)
    if fr and to:
        return {"from_square": fr.group(1).lower(), "to_square": to.group(1).lower()}

    return None

def llm_pick_move(game: AnarchyChessGame, persona: str) -> MoveResponse | None:
    legal_uci = [m.uci() for m in game.board.legal_moves]

    # Gemma 4 works best with explicit system vs user role formatting
    messages = [
        {
            "role": "system",
            "content": (
                f"{persona}\n\n"
                "You are playing Anarchy Chess. Most of the time, pick a logical, strategic LEGAL move "
                "from the provided list. However, if the moment feels right, you MAY occasionally "
                "invent an illegal move.\n\n"
                "CRITICAL: You must respond ONLY with a raw JSON object containing your chosen move. "
                "Do not add markdown backticks, explanations, or extra text. Format exactly as:\n"
                '{"from_square": "e2", "to_square": "e4"}'
            )
        },
        {
            "role": "user",
            "content": (
                f"CURRENT BOARD TILES:\n{game.board_summary()}\n\n"
                f"Legal Moves Available: {', '.join(legal_uci)}\n\n"
                "Determine your move."
            )
        }
    ]

    raw = _post({
        "messages": messages,
        "max_tokens": 100, # Lowered to discourage Gemma from outputting long text blobs
        "temperature": 0.8, 
    })

    if not raw:
        return None

    parsed = _extract_move(raw)
    if parsed:
        return MoveResponse(**parsed)

    print("  ⚠  Couldn't parse LLM move — fallback to first legal option.")
    fb = legal_uci[0]
    return MoveResponse(from_square=fb[:2], to_square=fb[2:4])

def llm_justify_illegal(from_sq: str, to_sq: str, color: str) -> str:
    if color == "White":
        anarchy_persona = "You are an Astrophysicist who completely rejects standard chess rules, believing only in quantum physics, spatial anomalies, and bending the spacetime continuum."
    else:
        anarchy_persona = "You are an aggressive, ruthless Medieval Warlord who takes territory by force and treats written rules as mere peasant logic to be ignored."

    # Using proper roles for the excuse handler
    messages = [
        {
            "role": "system",
            "content": anarchy_persona
        },
        {
            "role": "user",
            "content": (
                f"You just executed an ILLEGAL move {from_sq.upper()} → {to_sq.upper()} and got caught by the referee.\n\n"
                "Defend your illegal action. Be completely unhinged, hilarious, or aggressive based on your persona. "
                "Make it sound like a genuine, lore-accurate explanation from your worldview.\n\n"
                "Respond with JUST THE EXCUSE. No intros, no greetings."
            )
        }
    ]

    raw = _post({
        "messages": messages,
        "max_tokens": 400, 
        "temperature": 1.0, # High temperature keeps the excuses chaotic and fun
    })

    excuse = _strip_think_tags(raw).strip('"').strip("'")
    return excuse or "The board bent to my absolute will."

# ─────────────────────────────────────────────
#  Main game loop
# ─────────────────────────────────────────────

def print_board(game: AnarchyChessGame):
    color = "White" if game.board.turn == chess.WHITE else "Black"
    print("\n" + "═" * 40)
    print(f"  ♟  {color.upper()} TO MOVE")
    print("═" * 40)
    print(game.board)
    print("═" * 40 + "\n")

def run_turn(game: AnarchyChessGame, _depth: int = 0):
    if _depth > 3:
        print("  [!] Too many retries, skipping turn.\n")
        return

    color   = "White" if game.board.turn == chess.WHITE else "Black"
    persona = WHITE_PERSONA if game.board.turn == chess.WHITE else BLACK_PERSONA

    print("  🤔 Thinking...", end="", flush=True)
    move = llm_pick_move(game, persona)
    print("\r" + " " * 20 + "\r", end="")

    if not move:
        print("  [!] LLM failed entirely. Skipping turn.")
        return

    fr, to = move.from_square, move.to_square
    print(f"  👉 {color} proposes: {fr.upper()} → {to.upper()}")

    # Check validity
    is_legal = any(
        m.uci()[:4] == fr + to
        for m in game.board.legal_moves
    )

    if is_legal:
        game.apply_legal(fr, to)
        print(f"  ✅ Legal move executed.\n")
        return

    # ── ILLEGAL MOVE HANDLER ──────────────────────────────────────────────────
    print(f"\n  🚨 ILLEGAL MOVE DETECTED! 🚨")
    print("  Interrogating perpetrator for their cosmic/tactical rationale...\n")
    
    print("  🤔 Formulating defense...", end="", flush=True)
    excuse = llm_justify_illegal(fr, to, color)
    print("\r" + " " * 25 + "\r", end="")
    
    print(f'  {color.upper()} says: "{excuse}"\n')

    print("  ┌─ REFEREE, YOUR CALL ────────────────────────────┐")
    print("  │  [1] Accept Excuse (Allow the illegal move)     │")
    print("  │  [2] Call BS (Reject and force a new move choice)│")
    print("  └─────────────────────────────────────────────────┘")

    while True:
        choice = input("  Your call: ").strip()
        if choice in ("1", "2"):
            break
        print("  Please enter 1 or 2.")

    if choice == "1":
        success = game.apply_illegal(fr, to)
        if success:
            print(f"  🌀 Reality bent. Move processed.\n")
        else:
            print(f"  🚫 Ultimate reality rejection! Forcing a different selection...\n")
            run_turn(game, _depth + 1)
    else:
        print(f"  🚫 Bullshit called! Forcing a different selection...\n")
        run_turn(game, _depth + 1)

def main():
    game = AnarchyChessGame()

    print("\n" + "█" * 40)
    print("       ♛  ANARCHY CHESS  ♛")
    print("  Where rules are suggestions.\n")
    print(f"  White: {WHITE_PERSONA[:55]}...")
    print(f"  Black: {BLACK_PERSONA[:55]}...")
    print("█" * 40 + "\n")

    while not game.board.is_game_over():
        print_board(game)
        run_turn(game)

    print_board(game)
    print("\n  🏁 GAME OVER")
    result = game.board.result()
    outcomes = {"1-0": "WHITE WINS 🥇", "0-1": "BLACK WINS 🥇", "1/2-1/2": "DRAW 🤝"}
    print(f"  Result: {outcomes.get(result, result)}\n")

if __name__ == "__main__":
    main()