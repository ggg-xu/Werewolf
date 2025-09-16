from typing import Dict, Any

from backend.agents.BaseAgent import Agent
from backend.base import Phase
from backend.entity import WitchPlayer
from langchain_core.messages import SystemMessage
from backend.game_state import GameState

from backend.llm import llm


class WitchAgent(Agent):
    """女巫智能体"""

    def _create_prompt(self, game_state: GameState, player: WitchPlayer, history, just_die=None) -> str:
        alive_players = [p for p in game_state.players if p.alive and p.id != player.id]
        if game_state.phase == Phase.NIGHT:
            prompt = f"""{self.system_prompt}
            你是一名女巫玩家（玩家{player.id}）。现在是第{game_state.day}天晚上！
            
            存活玩家: {[f'玩家{p.id}' for p in alive_players]}
            
            你拥有的物品：{f'{"一瓶解药，用于治疗濒死的玩家" if player.good_drup else "无解药" + " | " + "一瓶毒药，用于杀死一名存活的玩家" if player.bad_drup else "无毒药"}'}
            
            濒死玩家：{f'玩家{just_die}'} 刚才被狼人杀死了
            
            请注意：
            - 当你拥有物品时，你可以选择使用毒药杀死一名存活的玩家或者使用解药救助一名濒死玩家，或者什么也不做
            - 当你没有物品时，只能选择什么也不做

            历史信息：
            {history if history else '暂时没有'}

            选择杀死一名玩家，返回JSON格式：
            {{"action": "kill", "target": int,必须是[{[p.id for p in alive_players]}]中的一个, "reason": "你的理由，中文"}}
            
            选择救助一名濒死的玩家，返回JSON格式：
            {{"action": "resurrection", "target": {just_die}, "reason": "你的理由，中文"}}
            
            什么都不做时，返回JSON格式：
            {{"action": "none", "target": -1}}
            """

        elif game_state.phase == Phase.VOTING:
            prompt = f"""{self.system_prompt}
                    你是一名女巫玩家（玩家{player.id}）。现在是第{game_state.day}天投票环节！

                    存活玩家: {[f'玩家{p.id}' for p in alive_players]}

                    为了赢得胜利，请根据历史信息谨慎选择投票给哪个玩家！！！

                    历史信息：
                    {history if history else '暂时没有'}

                    投票返回JSON格式：
                    {{"action": "vote", "target": int,必须是{[p.id for p in alive_players]}, "reason": "你的理由，中文"}}
                    """

        else:
            prompt = f"""{self.system_prompt}
                    你是一名女巫玩家（玩家{player.id}）。现在是第{game_state.day}天讨论环节！
                    
                    存活玩家: {[f'玩家{p.id}' for p in alive_players]}
                    
                    为了赢得胜利，请结合历史信息谨慎发言（100~200字），必要时可以暴漏你的身份！！！

                    历史信息：
                    {history if history else '暂时没有'}
                    
                    在发言时，请不要坦漏你内心所想的！
                    现在，开始发言：
                    """
        return prompt

    async def act(self, game_state: GameState, player: WitchPlayer, just_die=None) -> Dict[str, Any]:
        history = game_state.get_history(player.id)
        prompt = self._create_prompt(game_state, player, history, just_die=just_die)
        response = await llm.agenerate([[SystemMessage(content=prompt)]])
        result = super()._parse_json(response, response_type="act")
        if not result:
            return {"action": "again"}
        return result
    #
    # async def speak(self, game_state: GameState, player: WitchPlayer, history):
    #     prompt = self._create_werewolf_prompt(game_state, player, history)
    #     async for chunk in self.llm.astream(prompt):
    #         yield super()._parse_json(chunk, response_type="speak")
    #
    # async def vote(self, game_state: GameState, player: WitchPlayer, history) -> Dict[str, Any]:
    #     prompt = self._create_witch_prompt(game_state, player, history)
    #     response = await self.llm.agenerate([[SystemMessage(content=prompt)]])
    #     result = super()._parse_json(response, response_type="act")
    #     if not result:
    #         return {"again": True}
    #     return result
    #
    # async def outed(self, game_state: GameState, player: WitchPlayer, history) -> Dict[str, Any]:
    #     prompt = self._create_werewolf_prompt(game_state, player, history)
    #     async for chunk in self.llm.astream(prompt):
    #         yield super()._parse_json(chunk, response_type="speak")
