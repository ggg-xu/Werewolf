from pydantic import BaseModel
from backend.base import Role


class Player(BaseModel):
    id: int
    name: str
    role: Role
    alive: bool = True


class WitchPlayer(Player):
    good_drup: int = 1
    bad_drup: int = 1


