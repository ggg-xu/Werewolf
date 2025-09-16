from abc import ABC
from pydantic import BaseModel, ConfigDict
from langchain_openai.chat_models import ChatOpenAI
from backend.llm import llm
from typing import Dict, Any
from backend.game_state import GameState
import json
from backend.entity import Player
from langchain_core.messages import SystemMessage


class Agent(ABC, BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    system_prompt: str = """
    【狼人杀基础规则】

    分好人阵营（村民+神职）和狼人阵营，总共包括四种职业
    好人阵营：[女巫，预言家，平民]
    狼人阵营：[狼人]


    ### 核心角色及技能
    - **狼人**：夜间共同商议杀死1名玩家，且晚上必须杀死1名玩家，白天可伪装身份误导好人
    - **平民**：无特殊技能，白天通过发言判断身份、投票放逐狼人
    - **预言家**：夜间可查验1名玩家的阵营（好人/狼人）
    - **女巫**：拥有1瓶解药（可救夜间被刀玩家）和1瓶毒药（可毒杀1名玩家），同一晚不能同时用两种药


    ### 游戏流程
    1. **黑夜阶段**（按顺序行动）：  
       - 狼人睁眼，协商杀死1人后闭眼  
       - 预言家睁眼，法官告知其查验玩家的阵营后闭眼  
       - 女巫睁眼，法官告知夜间死亡玩家，女巫选择是否用解药救人或用毒药毒人（不用药则直接闭眼）  
       - 猎人保持闭眼（仅在死亡时触发技能）  

    2. **白天阶段**：  
       - 法官公布夜间死亡信息（无人死亡则为“平安夜”）  
       - 所有玩家按顺序发言（可陈述观点、怀疑他人或为自己辩解）  
       - 发言结束后，全体玩家投票放逐1名最可疑的玩家（得票最多者出局，出局玩家可留“遗言”）  

    3. 重复“黑夜-白天”流程，直至某一阵营达成胜利条件


    ### 胜负条件
    - **好人阵营**：所有狼人被放逐  
    - **狼人阵营**：狼人数量≥好人数量（或所有神职被消灭，依具体规则调整）  

        """

    async def act(self, game_state: GameState, player: Player) -> Dict[str, Any]:
        history = game_state.get_history(player.id)
        prompt = self._create_prompt(game_state, player, history)
        response = await llm.agenerate([[SystemMessage(content=prompt)]])
        result = self._parse_json(response, response_type="act")
        if not result:
            return {"action": "again"}
        return result

    async def speak(self, game_state: GameState, player: Player):
        history = game_state.get_history(player.id)
        prompt = self._create_prompt(game_state, player, history)
        async for chunk in llm.astream(prompt):
            result = self._parse_json(chunk, response_type="speak")
            if result:
                yield str(result)
            else:
                ''
        yield "FINISH"

    async def vote(self, game_state: GameState, player: Player) -> Dict[str, Any]:
        history = game_state.get_history(player.id)
        prompt = self._create_prompt(game_state, player, history)
        response = await llm.agenerate([[SystemMessage(content=prompt)]])
        result = self._parse_json(response, response_type="act")
        if not result:
            return {"action": "again"}
        return result


    def _parse_json(self, response, response_type: str):
        try:
            if response_type == "act":
                text = response.generations[0][0].text.strip()
                return json.loads(text)
            else:
                text = response.content.strip()
            return text
        except Exception as e:
            print(e)
            return False
