import chess
import json
import requests
import re
from pydantic import BaseModel, Field

# --- JSON Schema for LLM Output ---
class MoveResponse(BaseModel):
    explanation: str = Field(description="Your in-character explanation or trash talk for the move.")
    from_square: str = Field(description="The starting square, e.g., 'c1'")
    to_square: str = Field(description="The destination square, e.g., 'c5'")

# --- State Management ---
class AnarchyChessGame:
    def __init__(self):
        self.board = chess.Board()
        self.chaos_board = self._init_chaos_board()
        self.illegal_allowed = True 
        
    def _init_chaos_board(self):
        chaos = {}
        for square in chess.SQUARES:
            sq_name = chess.square_name(square)
            piece = self.board.piece_at(square)
            if piece:
                color = "White" if piece.color == chess.WHITE else "Black"
                name = chess.piece_name(piece.piece_type).title()
                chaos[sq_name] = f"{color} {name}"
            else:
                chaos[sq_name] = None
        return chaos

    def generate_board_chronicle(self):
        white_pieces = []
        black_pieces = []
        for square, piece_desc in self.chaos_board.items():
            if not piece_desc: continue
            if "White" in piece_desc:
                white_pieces.append(f"{piece_desc} on {square.upper()}")
            else:
                black_pieces.append(f"{piece_desc} on {square.upper()}")
        chronicle = "[CURRENT BOARD CHRONICLE]\n"
        chronicle += "- Your pieces: " + ", ".join(white_pieces if self.board.turn == chess.WHITE else black_pieces) + "\n"
        chronicle += "- Enemy pieces: " + ", ".join(black_pieces if self.board.turn == chess.WHITE else white_pieces) + "\n"
        if not self.illegal_allowed:
            chronicle += "\n[SYSTEM OVERRIDE]: The Chess Gods are watching. You MUST play a STRICTLY LEGAL move this turn."
        return chronicle

    def execute_turn(self, move_data: MoveResponse):
        try:
            from_sq_str = move_data.from_square.lower().strip()
            to_sq_str = move_data.to_square.lower().strip()
            from_sq = chess.parse_square(from_sq_str)
            to_sq = chess.parse_square(to_sq_str)
            attempted_move = chess.Move(from_sq, to_sq)
            piece = self.board.piece_at(from_sq)
            if piece and piece.piece_type == chess.PAWN:
                if (piece.color == chess.WHITE and chess.square_rank(to_sq) == 7) or \
                   (piece.color == chess.BLACK and chess.square_rank(to_sq) == 0):
                    attempted_move = chess.Move(from_sq, to_sq, promotion=chess.QUEEN)

            if attempted_move in self.board.legal_moves:
                print(f"\n[Legal Move by {'White' if self.board.turn == chess.WHITE else 'Black'}]: {move_data.explanation}")
                self.board.push(attempted_move)
                self._update_chaos_board(from_sq_str, to_sq_str)
                self.illegal_allowed = True
                return True

            print(f"\n🚨 ILLEGAL MOVE DETECTED! 🚨")
            print(f"Explanation: {move_data.explanation}")
            if not self.illegal_allowed:
                print("System: Anti-Entropy Cap reached. Move rejected.")
                return False
            ref_decision = input("\nReferee - [1] Buy the Excuse  [2] Call BS: ")
            if ref_decision == "1":
                print("Referee bought it! Bending reality...")
                piece_to_move = self.board.piece_at(from_sq)
                if piece_to_move:
                    self.board.remove_piece_at(from_sq)
                    self.board.set_piece_at(to_sq, piece_to_move)
                else:
                    print("No piece there! Reality broke too much.")
                    return False
                self.board.turn = not self.board.turn
                self._update_chaos_board(from_sq_str, to_sq_str)
                self.illegal_allowed = False
                return True
            else:
                print("Referee called BS! Move rejected.")
                return False
        except Exception as e:
            print(f"Error parsing move: {e}")
            return False

    def _update_chaos_board(self, from_sq, to_sq):
        self.chaos_board[to_sq] = self.chaos_board.get(from_sq)
        self.chaos_board[from_sq] = None


URL = "https://pushkarsharma-rtm--nemotron-chess-backend-api.modal.run"


def extract_move_from_text(text: str, legal_moves_uci: list[str]) -> dict | None:
    """
    Three strategies, in order:
      1. Find a valid JSON block with our three fields
      2. Find explicit UCI square pairs mentioned in text that match a legal move
      3. Find SAN notation (Nf6, e5, etc.) in text and match to legal moves
    """
    # ── Strategy 1: JSON extraction with proper brace matching ──────────────
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    candidates = []
    for match in re.finditer(r'\{', cleaned):
        start = match.start()
        depth = 0
        for i, ch in enumerate(cleaned[start:], start):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidates.append(cleaned[start:i+1])
                    break

    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if all(k in parsed for k in ("explanation", "from_square", "to_square")):
                return parsed
        except json.JSONDecodeError:
            continue

    # ── Strategy 2: Find UCI pairs (e2e4, g8f6, etc.) in the prose ──────────
    # Model often writes things like "g8->f6", "g8 to f6", "g8-f6", "Nf6 (g8f6)"
    uci_pattern = re.findall(r'\b([a-h][1-8])\s*(?:->|-|to)\s*([a-h][1-8])\b', cleaned, re.IGNORECASE)
    for from_sq, to_sq in uci_pattern:
        uci = from_sq.lower() + to_sq.lower()
        if uci in legal_moves_uci:
            return {"explanation": f"Move {from_sq}->{to_sq}", "from_square": from_sq.lower(), "to_square": to_sq.lower()}

    # Also check bare UCI strings like "g8f6"
    bare_uci = re.findall(r'\b([a-h][1-8])([a-h][1-8])\b', cleaned, re.IGNORECASE)
    for from_sq, to_sq in bare_uci:
        uci = from_sq.lower() + to_sq.lower()
        if uci in legal_moves_uci:
            return {"explanation": f"Move {from_sq}{to_sq}", "from_square": from_sq.lower(), "to_square": to_sq.lower()}

    # ── Strategy 3: Field-level regex (JSON fields exist but not valid JSON) ─
    explanation = re.search(r'"explanation"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    from_m = re.search(r'"from_square"\s*:\s*"([a-h][1-8])"', cleaned, re.IGNORECASE)
    to_m   = re.search(r'"to_square"\s*:\s*"([a-h][1-8])"', cleaned, re.IGNORECASE)
    if from_m and to_m:
        uci = from_m.group(1).lower() + to_m.group(1).lower()
        if uci in legal_moves_uci:
            return {
                "explanation": explanation.group(1) if explanation else "...",
                "from_square": from_m.group(1).lower(),
                "to_square":   to_m.group(1).lower(),
            }

    return None


def get_llm_move(game: AnarchyChessGame, persona_prompt: str):
    board_state_text = game.generate_board_chronicle()
    color_playing = "White" if game.board.turn == chess.WHITE else "Black"

    # Give ALL legal moves in UCI format — model's reasoning will reference these squares
    legal_moves_uci = [m.uci() for m in game.board.legal_moves]
    # Also show a few in SAN for readability
    legal_sample_san = [game.board.san(m) for m in list(game.board.legal_moves)[:10]]

    system_prompt = f"""{persona_prompt}

                {board_state_text}

                Legal moves (SAN): {', '.join(legal_sample_san)}
                Legal moves (UCI from->to): {', '.join(legal_moves_uci)}

                INSTRUCTIONS:
                You may choose a valid legal move from the list above, OR you can completely ignore the rules and invent an illegal move that fits your persona (e.g., teleporting a piece, capturing your own piece for a sacrifice, skipping over pawns). 

                If you make an illegal move, use the 'explanation' field to aggressively gaslight the human referee into thinking your move makes perfect sense.

                Be as funny as you can while explaining your illegal move everything is valid

                YOU MUST RESPOND WITH ONLY THIS JSON:
                {{"explanation": "your in-character reasoning/gaslighting", "from_square": "XX", "to_square": "XX"}}"""
    payload = {
        "messages": [{"role": "user", "content": system_prompt}],
        "max_tokens": 2048,  # Short on purpose — we only need one JSON object
        "temperature": 0.7
    }

    try:
        response = requests.post(URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        response_text = data.get('response', str(data))

        parsed = extract_move_from_text(response_text, legal_moves_uci)
        if parsed:
            return MoveResponse(**parsed)

        # ── Last resort: just pick the first legal move ──────────────────────
        # This only fires if ALL extraction strategies fail (should be very rare)
        print(f"⚠️  Could not parse any move from LLM output. Using first legal move as fallback.")
        print(f"Raw output was:\n{response_text[:300]}...")
        fallback = legal_moves_uci[0]
        return MoveResponse(
            explanation="(fallback: LLM output unparseable)",
            from_square=fallback[:2],
            to_square=fallback[2:4]
        )

    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def main():
    game = AnarchyChessGame()
    white_persona = "You are a competitive chess AI. Explain your move logically."
    black_persona = "You are a competitive chess AI. Explain your move logically."

    print("Welcome to Anarchy Chess!")
    print("-------------------------")

    while not game.board.is_game_over():
        print("\n" + "="*30)
        print(f"Turn: {'White' if game.board.turn == chess.WHITE else 'Black'} to move")
        print(game.board)
        print("="*30 + "\n")

        if game.board.turn == chess.WHITE:
            persona_prompt = "You are an Astryphysicst you don't belive in the laws of the game you only believe in physics and according to you anything can happen."
        else:
            persona_prompt = "You are a ruthless Medieval Warlord. You conquer the board by force, ignoring the laws of physics if necessary."
        print("Thinking...")
        move_data = get_llm_move(game, persona_prompt)

        if move_data:
            print(f"\nMove proposed: {move_data.from_square} -> {move_data.to_square}")
            success = game.execute_turn(move_data)
            if not success:
                print("Retrying turn...")
        else:
            print("Failed to get a move from the LLM. Retrying...")

    print("Game Over!")
    print(game.board.result())

if __name__ == "__main__":
    main()