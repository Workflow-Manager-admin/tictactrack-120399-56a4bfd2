from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional, List
from uuid import uuid4
import hashlib
import secrets
import time
from .models import (
    UserAuthRequest,
    UserAuthResponse,
    GameCreateRequest,
    GameCreateResponse,
    GameJoinRequest,
    GameJoinResponse,
    MoveRequest,
    MoveResponse,
    GameStateResponse,
    GameHistoryResponse,
    GameHistoryItem,
)

app = FastAPI(
    title="Tic Tac Toe Backend API",
    description="APIs for Tic Tac Toe Game: Auth, Game Logic, State, Results, and History",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "User registration and authentication."},
        {"name": "game", "description": "Game create/join, moves, board state, results."},
        {"name": "history", "description": "User game history and results."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# --- In-memory stores (replace with DB in prod) ---
USERS: Dict[str, dict] = {}
TOKENS: Dict[str, str] = {}  # token -> user_id
GAMES: Dict[str, dict] = {}
MOVES: Dict[str, List[dict]] = {}  # game_id -> list of moves
USER_HISTORY: Dict[str, List[dict]] = {}


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def gen_token(length=32) -> str:
    return secrets.token_hex(length // 2)


def get_user_id_by_token(token: str) -> Optional[str]:
    return TOKENS.get(token)


# Dependency for authentication
def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    user_id = get_user_id_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")
    return user_id

# --- Helper: check win state ---
def check_winner(board: List[Optional[str]]) -> Optional[str]:
    wins = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
        [0, 4, 8], [2, 4, 6],             # diagonals
    ]
    for i, j, k in wins:
        if board[i] is not None and board[i] == board[j] == board[k]:
            return board[i]  # "X" or "O"
    return None


# --- API ROUTES ---

# PUBLIC_INTERFACE
@app.post("/auth/register", summary="Register a user", tags=["auth"], response_model=UserAuthResponse)
def register(request: UserAuthRequest):
    """Register a new user. Returns token if successful."""
    if request.username in (u["username"] for u in USERS.values()):
        raise HTTPException(status_code=400, detail="Username already exists")
    user_id = str(uuid4())
    USERS[user_id] = {
        "username": request.username,
        "password_hash": hash_pw(request.password),
        "created_at": time.time(),
        "user_id": user_id,
    }
    token = gen_token()
    TOKENS[token] = user_id
    USER_HISTORY[user_id] = []
    return UserAuthResponse(user_id=user_id, username=request.username, token=token)

# PUBLIC_INTERFACE
@app.post("/auth/login", summary="Login user", tags=["auth"], response_model=UserAuthResponse)
def login(request: UserAuthRequest):
    """Authenticate user and return token."""
    for user_id, rec in USERS.items():
        if rec["username"] == request.username and rec["password_hash"] == hash_pw(request.password):
            token = gen_token()
            TOKENS[token] = user_id
            return UserAuthResponse(user_id=user_id, username=rec["username"], token=token)
    raise HTTPException(status_code=401, detail="Invalid credentials")

# PUBLIC_INTERFACE
@app.post("/game/create", summary="Create a new game", tags=["game"], response_model=GameCreateResponse)
def create_game(request: GameCreateRequest, user_id: str = Depends(require_auth)):
    """Creates a new Tic Tac Toe game lobby. Only the creator is present initially."""
    game_id = str(uuid4())
    game = {
        "game_id": game_id,
        "creator_id": user_id,
        "players": [user_id],
        "symbols": {user_id: "X"},  # creator always gets "X"
        "board": [None] * 9,
        "turn": user_id,
        "status": "waiting",  # waiting, ongoing, finished
        "winner": None,
        "created_at": time.time(),
        "moves": [],
        "opponent_id": None,
    }
    GAMES[game_id] = game
    MOVES[game_id] = []
    return GameCreateResponse(game_id=game_id, creator_id=user_id, status=game["status"])

# PUBLIC_INTERFACE
@app.post("/game/join", summary="Join a game", tags=["game"], response_model=GameJoinResponse)
def join_game(request: GameJoinRequest, user_id: str = Depends(require_auth)):
    """Join a waiting game lobby. Fails if game is full or started."""
    game = GAMES.get(request.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if len(game["players"]) >= 2:
        raise HTTPException(status_code=400, detail="Game already full")
    if game["status"] != "waiting":
        raise HTTPException(status_code=400, detail="Game is not joinable")
    game["players"].append(user_id)
    game["symbols"][user_id] = "O"
    game["status"] = "ongoing"
    game["opponent_id"] = user_id
    return GameJoinResponse(game_id=game["game_id"], symbol="O", status=game["status"])

# PUBLIC_INTERFACE
@app.get("/game/{game_id}/state", summary="Get current board state", tags=["game"], response_model=GameStateResponse)
def get_state(game_id: str, user_id: str = Depends(require_auth)):
    """Get the current board state, players, turn, and winner."""
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    usernames = [USERS[p]["username"] for p in game["players"]]
    turn_username = USERS[game["turn"]]["username"] if game["turn"] in USERS else None
    winner = USERS[game["winner"]]["username"] if game["winner"] and game["winner"] in USERS else None
    return GameStateResponse(
        game_id=game_id,
        board=game["board"],
        players=usernames,
        turn=turn_username,
        status=game["status"],
        winner=winner,
    )

# PUBLIC_INTERFACE
@app.post("/game/move", summary="Make a move in a game", tags=["game"], response_model=MoveResponse)
def make_move(request: MoveRequest):
    """Make a move in an ongoing game. Validates turn and win state, handles draw."""
    token = request.token
    user_id = get_user_id_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Auth failed")

    game = GAMES.get(request.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game["status"] != "ongoing":
        raise HTTPException(status_code=400, detail="Game is not active")
    if user_id not in game["players"]:
        raise HTTPException(status_code=403, detail="Not a participant of this game")
    if game["turn"] != user_id:
        raise HTTPException(
            status_code=400,
            detail="Not your turn. Wait for other player."
        )
    pos = request.position
    if game["board"][pos] is not None:
        raise HTTPException(status_code=400, detail="Cell already occupied.")

    symbol = game["symbols"][user_id]
    game["board"][pos] = symbol
    MOVES[game["game_id"]].append({"user_id": user_id, "position": pos, "symbol": symbol, "timestamp": time.time()})
    game["moves"].append(pos)

    winner_symbol = check_winner(game["board"])
    if winner_symbol:
        # Find user_id of winner:
        for pid, s in game["symbols"].items():
            if s == winner_symbol:
                game["status"] = "finished"
                game["winner"] = pid
                break
    elif all(cell is not None for cell in game["board"]):
        game["status"] = "finished"
        game["winner"] = None  # Draw

    # Advance turn
    if game["status"] != "finished":
        other_players = [pid for pid in game["players"] if pid != user_id]
        game["turn"] = other_players[0] if other_players else user_id
    else:
        game["turn"] = None

        # Save to history
        for pid in game["players"]:
            if pid in USER_HISTORY:
                USER_HISTORY[pid].append({
                    "game_id": game["game_id"],
                    "opponent": USERS[other_players[0]]["username"] if other_players and other_players[0] in USERS else None,
                    "result": ("win" if pid == game["winner"] else "loss") if game["winner"] else "draw",
                    "moves": len(game["moves"]),
                    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })

    winner_id = game["winner"]
    winner_username = USERS[winner_id]["username"] if winner_id and winner_id in USERS else None

    return MoveResponse(
        board=game["board"],
        next_turn=game["turn"],
        status=game["status"] if game["status"] != "finished" else ("draw" if not winner_id else (f"{symbol}_wins")),
        winner=winner_username,
    )

# PUBLIC_INTERFACE
@app.get("/user/history", summary="Get user game history", tags=["history"], response_model=GameHistoryResponse)
def get_history(user_id: str = Depends(require_auth)):
    """Returns a list of completed games with outcome and moves."""
    user_games = USER_HISTORY.get(user_id, [])
    return GameHistoryResponse(user_id=user_id, games=[GameHistoryItem(**g) for g in user_games])


@app.get("/", summary="API Health Check", tags=["auth"])
def health_check():
    """Health check endpoint for service monitoring."""
    return {"message": "Healthy"}

