from typing import List, Dict, Optional
import random
from backend.events import (
    Event,
    SystemEvent,
    PlayerEvent,
    DisplayEvent,
    AllowActEvent,
    AllowVoteEvent,
    AllowSpeakEvent,
    DayChangeEvent,
    PhaseChangeEvent
)
from backend.entity import *
from backend.base import *


class GameState(BaseModel):
    players: List[Player] = [None] * 6
    phase: Phase = Phase.NIGHT
    conversations: int = 1
    day: int = 1
    events: List[Event] = []
    histories: Dict[int, List[Event]] = {}
    alive_players: List[int] = []
    just_killed: List[int] = []
    speak_order: List[int] = [None] * 6
    act_order: List[int] = [None] * 4
    game_over: bool = False
    winner: Optional[str] = None
    step: int = 0
    out: int = 0
    votes: List[int] = [0] * 6
    phase_map: Dict[Phase, str] = {
        Phase.DAY: "白天",
        Phase.NIGHT: "夜晚",
        Phase.DISCUSSION: "讨论环节",
        Phase.VOTING: "投票环节",
        Phase.COUNT_VOTES: "计票环节",
    }
    role_map: Dict[Role, str] = {
        Role.WEREWOLF: "werewolf",
        Role.SEER: "seer",
        Role.WITCH: "witch",
        Role.VILLAGER: "villager"
    }

    def initialize_players(self):
        roles = [Role.WEREWOLF, Role.WEREWOLF, Role.VILLAGER,
                 Role.VILLAGER, Role.SEER, Role.WITCH]
        random.shuffle(roles)

        self.players = [
            Player(id=i + 1, name=f"玩家{i + 1}", role=role)
            if role != Role.WITCH
            else WitchPlayer(id=i + 1, name=f"玩家{i + 1}", role=role)
            for i, role in enumerate(roles)
        ]
        # 初始化行动顺序（狼人、狼人、预言家、女巫）
        act_roles = [Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.WITCH]
        self.act_order = []
        for role in act_roles:
            # 找到对应角色的存活玩家（处理可能的重复角色）
            for player in self.players:
                if player.role == role and player.id not in self.act_order:
                    self.act_order.append(player.id)
                    break

        for i in range(0, 7):
            self.histories[i] = []

        self.alive_players = [p.id for p in self.players]
        self.speak_order = self.alive_players.copy()
        self.events = self.must_event_every_day()

    def must_event_every_day(self):
        return [PhaseChangeEvent(day=self.day, phase=Phase.NIGHT, change=Phase.DAY)] + \
            [AllowActEvent(day=self.day, phase=Phase.NIGHT, target=i) for i in reversed(self.act_order)] + \
            [DisplayEvent(day=self.day, phase=Phase.NIGHT,
                          content=f"第{self.day}天夜晚，存活的玩家为{' | '.join([f'玩家{i}' for i in self.alive_players])}")]

    def add_event(self, event: Event):
        self.events.append(event)

    def when_day_event(self):
        self.events = [PhaseChangeEvent(day=self.day, phase=Phase.VOTING, change=Phase.COUNT_VOTES)] + \
                      [AllowVoteEvent(day=self.day, phase=Phase.VOTING, target=i) for i in reversed(self.speak_order)] + \
                      [DisplayEvent(day=self.day, phase=Phase.VOTING, content=f"现在是投票环节")] + \
                      [PhaseChangeEvent(day=self.day, phase=Phase.DISCUSSION, change=Phase.VOTING)] + \
                      [AllowSpeakEvent(day=self.day, phase=Phase.DISCUSSION, target=i) for i in
                       reversed(self.speak_order)] + \
                      [DisplayEvent(day=self.day, phase=Phase.DISCUSSION, content=f"现在是讨论环节")] + \
                      [PhaseChangeEvent(day=self.day, phase=Phase.DAY, change=Phase.DISCUSSION)] + \
                      [DisplayEvent(day=self.day, phase=Phase.DAY,
                                    content=f"现在是白天,昨晚{(' | '.join([f'玩家{i}' for i in self.just_killed]) + '被杀死了！') if self.just_killed else ('没有人死亡！')}")]

    def when_count_vote_event(self):
        self.events = [DayChangeEvent(day=self.day, phase=Phase.COUNT_VOTES)] + \
                      [DisplayEvent(day=self.day, phase=Phase.COUNT_VOTES, content=f"玩家{self.out}出局了")]

    def get_event(self):
        return self.events.pop(-1)

    def add_just_killed(self, player_id, sid=None):
        player = self.players[sid - 1]
        if player.role == Role.WITCH and player.bad_drup != 1:
            return
        if player_id not in self.just_killed:
            self.just_killed.append(player_id)
            if player.role == Role.WITCH:
                player.bad_drup = 0

    def resurrection(self, player_id, sid):
        if player_id in self.just_killed:
            self.just_killed.remove(player_id)
        player = self.players[sid - 1]
        player.good_drup = 0

    def kill_player(self):
        if not self.just_killed:
            return
        for player in self.players:
            if player.id in self.just_killed:
                player.alive = False
        self.act_order = [pid for pid in self.act_order if pid not in self.just_killed]
        self.alive_players = [p.id for p in self.players if p.alive]

    def vote(self, pid):
        self.votes[pid - 1] += 1

    def set_out(self):
        self.out = self.votes.index(max(self.votes)) + 1
        for player in self.players:
            if player.id == self.out:
                player.alive = False
        self.alive_players = [p.id for p in self.players if p.alive]

    def next_day(self):
        self.day += 1
        self.phase = Phase.NIGHT
        self.just_killed = []
        self.speak_order = self.alive_players.copy()
        self.events = self.must_event_every_day()
        self.votes = [0 for _ in range(6)]
        self.out = 0
        self.conversations = 1

    def check_game_over(self):
        werewolves_alive = sum(1 for p in self.players
                               if p.role == Role.WEREWOLF and p.alive)
        others_alive = sum(1 for p in self.players
                           if p.role != Role.WEREWOLF and p.alive)

        if werewolves_alive == 0:
            self.game_over = True
            self.winner = "好人阵营"
            return True
        elif werewolves_alive >= others_alive:
            self.game_over = True
            self.winner = "狼人阵营"
            return True
        return False

    def add_player_history(self, pid, content):
        self.histories[pid].append(PlayerEvent(day=self.day, phase=self.phase, content=content))

    def add_system_history(self, content):
        self.histories[0].append(SystemEvent(day=self.day, phase=self.phase, content=content))

    def get_history(self, pid):
        tmp = []
        tmp.extend([data for data in self.histories[pid] if data.phase == Phase.NIGHT])
        tmp.extend([data for data in self.histories[0] if
                    data.phase == Phase.DAY or data.phase == Phase.DISCUSSION or data.phase == Phase.VOTING])
        tmp = sorted(tmp, key=lambda x: x.day)
        history = [f"在第{data.day}天{data.phase}:{data.content}" for data in tmp]

        return "\n".join(history)
