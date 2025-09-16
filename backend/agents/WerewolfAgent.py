from typing import Dict, Any

from backend.agents.BaseAgent import Agent
from backend.base import Role, Phase
from backend.entity import Player
from langchain_core.messages import SystemMessage
from backend.game_state import GameState
from backend.llm import llm


class WerewolfAgent(Agent):
    """狼人智能体"""

    def _create_prompt(self, game_state: GameState, player: Player, history, content=None, count=0) -> str:
        alive_players = [p for p in game_state.players if p.alive and p.id != player.id]
        teammate = next((p for p in game_state.players
                         if p.role == Role.WEREWOLF and p.id != player.id and p.alive), None)
        if game_state.phase == Phase.NIGHT:
            prompt = f"""{self.system_prompt}
                        你是一名狼人玩家（玩家{player.id}）。现在是第{game_state.day}天晚上！
                        存活玩家: {[f'玩家{p.id}' for p in alive_players]}
                        你的队友: {'玩家' + str(teammate.id) if teammate else '已死亡'}
                        {('你的队友对你说：' + content) if content else ''}
                        你和你的队友每晚只能杀死一个玩家，请结合历史信息并和你的队友交流后谨慎选择！！！
                        
                        注意：
                        - 你要杀死所有非狼人玩家，已取得最终胜利
                        - 在每天，你最多能和队友总计交流 2 次，现在你已经和队友交流了{count - 1}次
                        - 当你和队友还有交流机会时，应优先选择和队友交流

                        历史信息：
                        {history if history else '暂时没有'}
                        
                        """ + \
                    f"""
                        请选择一名玩家作为猎杀目标或者和你的队友交流:
                        猎杀目标，返回JSON格式：
                        {{"action": "kill", "target": int,必须是{[p.id for p in alive_players]}中的一个, "reason": "你的理由，中文"}}

                        和队友交流，返回JSON格式：
                        {{"action": "conversation", "target": {teammate}, "content": "交流内容,中文"}}
                    """ if count < 3 and teammate else \
                    f"""
                        请选择一名玩家作为猎杀目标:
                        猎杀目标，返回JSON格式：
                        {{"action": "kill", "target": int,必须是{[p.id for p in alive_players]}中的一个, "reason": "你的理由"}}
                    """

        elif game_state.phase == Phase.VOTING:
            prompt = f"""{self.system_prompt}
                    你是一名狼人玩家（玩家{player.id}）。现在是第{game_state.day}天投票环节！

                    存活玩家: {[f'玩家{p.id}' for p in alive_players]}

                    为了赢得胜利，请根据历史信息谨慎选择投票给哪个玩家，必要时，你可以投给你的队友！！！

                    历史信息：
                    {history if history else '暂时没有'}

                    投票返回JSON格式：
                    {{"action": "vote", "target": int,必须是{[p.id for p in alive_players]}中的一个, "reason": "你的理由，中文"}}
                    """

        else:
            prompt = f"""{self.system_prompt}
                        你是一名狼人玩家（玩家{player.id}）。现在是第{game_state.day}天讨论环节。
                        存活玩家: {[f'玩家{p.id}' for p in alive_players]}
                        你的队友: {'玩家' + str(teammate.id) if teammate else '无'}
                        为了赢得胜利，请结合历史信息谨慎进行发言（100~200字），为了欺骗其他玩家，你可以伪装自己的身份（例如女巫、预言家、平民）！！！

                        历史信息：
                        {history if history else '暂时没有'}
                        
                        在发言时，请不要坦漏你内心所想的！
                        现在，开始发言：
                        """
        return prompt

    async def act(self, game_state: GameState, player: Player, content=None, count=0) -> Dict[str, Any]:
        prompt = self._create_prompt(game_state, player, content, count=count)
        response = await llm.agenerate([[SystemMessage(content=prompt)]])
        result = super()._parse_json(response, response_type="act")
        if not result:
            return {"action": "again"}
        return result
    #
    # async def speak(self, game_state: GameState, player: Player, history):
    #     prompt = self._create_werewolf_prompt(game_state, player, history)
    #     async for chunk in self.llm.astream(prompt):
    #         yield super()._parse_json(chunk, response_type="speak")
