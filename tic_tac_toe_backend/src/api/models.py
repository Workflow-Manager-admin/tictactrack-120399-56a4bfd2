"""
Models and schemas for Tic Tac Toe Backend.
Includes Pydantic models for users, game creation, moves, results, and game history.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# PUBLIC_INTERFACE
class UserAuthRequest(BaseModel):
    """User registration and authentication request."""
    username: str = Field(..., description="Username for the user.")
    password: str = Field(..., description="User's password.")


# PUBLIC_INTERFACE
class UserAuthResponse(BaseModel):
    """User authentication response containing user id and token."""
    user_id: str = Field(..., description="Unique user ID.")
    username: str = Field(..., description="Username.")
    token: str = Field(..., description="JWT or session token.")


# PUBLIC_INTERFACE
class GameCreateRequest(BaseModel):
    """Request for creating a new game."""
    game_name: str = Field(..., description="Display name for the game (lobby).")


# PUBLIC_INTERFACE
class GameCreateResponse(BaseModel):
    """Response containing game ID and initial state."""
    game_id: str = Field(..., description="ID of the new game.")
    creator_id: str = Field(..., description="ID of the game creator.")
    status: str = Field(..., description="Game status (e.g., waiting, ongoing, finished).")


# PUBLIC_INTERFACE
class GameJoinRequest(BaseModel):
    """Request to join a game."""
    game_id: str = Field(..., description="ID of the game to join.")


# PUBLIC_INTERFACE
class GameJoinResponse(BaseModel):
    """Response containing game info after joining."""
    game_id: str = Field(..., description="ID of the joined game.")
    symbol: Literal["X", "O"] = Field(..., description="Player's symbol (X or O).")
    status: str = Field(..., description="Game status after joining.")


# PUBLIC_INTERFACE
class MoveRequest(BaseModel):
    """Request to make a move in the game."""
    game_id: str = Field(..., description="Game ID.")
    position: int = Field(..., ge=0, le=8, description="Board position (0-8, left-right, top-bottom).")
    token: str = Field(..., description="User authentication token.")


# PUBLIC_INTERFACE
class MoveResponse(BaseModel):
    """Response after making a move."""
    board: List[Optional[str]] = Field(..., description="The updated board (list of symbols or None).")
    next_turn: Optional[str] = Field(..., description="Whose turn is next (user_id).")
    status: str = Field(..., description="Current status: ongoing, draw, X_wins, O_wins.")
    winner: Optional[str] = Field(None, description="user_id of winner (if finished).")


# PUBLIC_INTERFACE
class GameStateResponse(BaseModel):
    """Current state of the game."""
    game_id: str
    board: List[Optional[str]]  # 9-length board with "X"/"O"/None
    players: List[str]  # List of usernames
    turn: Optional[str]  # Username whose turn
    status: str
    winner: Optional[str]


# PUBLIC_INTERFACE
class GameHistoryItem(BaseModel):
    """An entry in the player's history."""
    game_id: str
    opponent: str
    result: str  # win/loss/draw
    moves: int
    finished_at: str  # ISO timestamp


# PUBLIC_INTERFACE
class GameHistoryResponse(BaseModel):
    """Response: List of games player has participated in."""
    user_id: str
    games: List[GameHistoryItem]

