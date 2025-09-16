from typing import Dict, Any

from backend.agents.BaseAgent import Agent
from backend.base import Role, Phase
from backend.entity import Player
from langchain_core.messages import SystemMessage
from backend.game_state import GameState


class SeerAgent(Agent):
    """预言家智能体"""

    def _create_prompt(self, game_state: GameState, player: Player, history) -> str:
        alive_players = [p for p in game_state.players if p.alive and p.id != player.id]
        if game_state.phase == Phase.NIGHT:
            prompt = f"""{self.system_prompt}
            你是一名预言家玩家（玩家{player.id}）。现在是第{game_state.day}天晚上！
            存活玩家: {[f'玩家{p.id}' for p in alive_players]}
            你需要尽快找到狼人，请根据历史信息分析哪个玩家可能狼人，并查验他的身份
            
            历史信息：
            {history if history else '暂时没有'}
            
            请选择一名玩家查验身份，返回JSON格式：
            {{"action": "check", "target": int,必须是{[p.id for p in alive_players]}中的一个, "reason": "你的理由，中文"}}
            """
        elif game_state.phase == Phase.VOTING:
            prompt = f"""{self.system_prompt}
                    你是一名预言家玩家（玩家{player.id}）。现在是第{game_state.day}天投票环节！

                    存活玩家: {[f'玩家{p.id}' for p in alive_players]}

                    为了赢得胜利，请根据历史信息谨慎选择投票给哪个玩家！！！

                    历史信息：
                    {history if history else '暂时没有'}

                    投票返回JSON格式：
                    {{"action": "vote", "target": int,必须是{[p.id for p in alive_players]}中的一个, "reason": "你的理由，中文"}}
                    """

        else:
            prompt = f"""{self.system_prompt}
                    你是一名预言家玩家（玩家{player.id}）。现在是第{game_state.day}天讨论环节。
                    存活玩家: {[f'玩家{p.id}' for p in alive_players]}
                    为了赢得胜利，请结合历史信息谨慎发言（100~200字），必要时可以暴漏你的身份！！！

                    历史信息：
                    {history if history else '暂时没有'}
                    
                    在发言时，请不要坦漏你内心所想的！
                    现在，开始发言：
                    """
        return prompt

    # async def act(self, game_state: GameState, player: Player, history) -> Dict[str, Any]:
    #     prompt = self._create_seer_prompt(game_state, player, history)
    #     response = await self.llm.agenerate([[SystemMessage(content=prompt)]])
    #     result = super()._parse_json(response, response_type="act")
    #     if not result:
    #         return {"again": True}
    #     return result
    #
    # async def speak(self, game_state: GameState, player: Player, history):
    #     prompt = self._create_seer_prompt(game_state, player, history)
    #     async for chunk in self.llm.astream(prompt):
    #         yield super()._parse_json(chunk, response_type="speak")
    #
    # async def vote(self, game_state: GameState, player: Player, history) -> Dict[str, Any]:
    #     prompt = self._create_seer_prompt(game_state, player, history)
    #     response = await self.llm.agenerate([[SystemMessage(content=prompt)]])
    #     result = super()._parse_json(response, response_type="act")
    #     if not result:
    #         return {"again": True}
    #     return result
    #
    # async def outed(self, game_state: GameState, player: Player, history) -> Dict[str, Any]:
    #     prompt = self._create_seer_prompt(game_state, player, history)
    #     async for chunk in self.llm.astream(prompt):
    #         yield super()._parse_json(chunk, response_type="speak")
