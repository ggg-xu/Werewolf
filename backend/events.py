from pydantic import BaseModel
from backend.base import Phase


class Event(BaseModel):
    etype: str
    day: int
    phase: Phase


class PlayerEvent(Event):
    # 用于记录玩家的历史信息
    etype: str = "PLAYER"
    content: str


class SystemEvent(Event):
    # 用于记录历史信息记录在在第几天，什么事件段，发生了什么时
    etype: str = "SYSTEM"
    content: str


class DisplayEvent(Event):
    etype: str = "DISPLAY"
    content: str


class ConversationEvent(Event):
    # 用于狼人玩家交流
    etype: str = "CONVERSATION"
    source: int  # 制定事件玩家ID
    target: int  # 玩家ID
    content: str  # 交流内容
    count: int  # 记录交流次数

    def to_string(self):
        return f"玩家{self.source}对玩家{self.target}说：{self.content}"


class KillEvent(Event):
    etype: str = "KILL"
    source: int  # 制定事件玩家ID
    target: int  # 玩家ID
    reason: str = None

    def to_string(self):
        return f"玩家{self.source}杀死了玩家{self.target}。"


class ResurrectionEvent(Event):
    # 用于女巫玩家用药救人
    etype: str = "RESURRECTION"
    source: int  # 制定事件玩家ID
    target: int  # 玩家ID
    reason: str = None

    def to_string(self):
        return f"玩家{self.source}拯救了玩家{self.target}。"


class CheckEvent(Event):
    # 用于预言家玩家验证玩家身份
    etype: str = "CHECK"
    source: int  # 制定事件玩家ID
    target: int  # 玩家ID
    reason: str = None

    def to_string(self):
        return f"玩家{self.source}检查了玩家{self.target}的身份。"


class VoteEvent(Event):
    # 用于玩家进行投票
    etype: str = "VOTE"
    source: int  # 制定事件玩家ID
    target: int  # 玩家ID
    reason: str = None

    def to_string(self):
        return f"玩家{self.source}投票给了玩家{self.target}。"


class AllowSpeakEvent(Event):
    etype: str = "ALLOW_SPEAK"
    target: int


class AllowActEvent(Event):
    etype: str = "ALLOW_ACT"
    target: int

    def to_string(self):
        return f"玩家{self.target}开始行动。"


class AllowVoteEvent(Event):
    etype: str = "ALLOW_VOTE"
    target: int

    def to_string(self):
        return f"玩家{self.target}开始投票。"


class PhaseChangeEvent(Event):
    etype: str = "PHASE_CHANGE"
    change: str = Phase

    def to_string(self):
        return f"当前环节为{self.change}。"


class DayChangeEvent(Event):
    etype: str = "DAY_CHANGE"
