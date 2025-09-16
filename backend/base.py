from enum import Enum


class Role(str, Enum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"


class Phase(str, Enum):
    NIGHT = "night"
    DAY = "day"
    DISCUSSION = "discussion"
    VOTING = "voting"
    COUNT_VOTES = "count_votes"
    # GAME_OVER = "game_over"


