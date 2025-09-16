from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from typing import Dict, Any
import uuid
import json
from contextlib import asynccontextmanager

from pydantic_core._pydantic_core import ValidationError

from backend.game_state import GameState
from backend.base import Role, Phase
from backend.agents import WerewolfAgent, SeerAgent, WitchAgent, VillagerAgent
from backend.events import (
    ConversationEvent,
    ResurrectionEvent,
    KillEvent,
    CheckEvent,
    VoteEvent,
    AllowActEvent
)


agents = {}
# 定义lifespan上下文管理器（替代原来的startup事件）
@asynccontextmanager
async def lifespan(app: FastAPI):
    """初始化代理（启动时执行）"""
    global agents  # 声明使用全局变量
    agents["werewolf"] = WerewolfAgent()
    agents["seer"] = SeerAgent()
    agents["witch"] = WitchAgent()
    agents["villager"] = VillagerAgent()
    yield  # 程序运行期间会停在这里

app = FastAPI(title="狼人杀游戏后端", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="../frontend/static"), name="/werewolf")

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局游戏状态和代理
game_states: Dict[str, GameState] = {}
game_events: Dict[str, asyncio.Event] = {}


def sse_event(data: dict, event_name: str = None) -> str:
    lines = []
    if event_name:
        lines.append(f"event: {event_name}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")  # 结尾空行
    lines.append("")
    return "\n".join(lines)

@app.get("/index")
async def index():
    return FileResponse('../frontend/qwen.html')
@app.get("/game/start")
async def start_game():
    """开始新游戏"""
    game_id = str(uuid.uuid4())
    game_state = GameState()
    game_events[game_id] = asyncio.Event()
    game_events[game_id].clear()

    game_state.initialize_players()
    game_states[game_id] = game_state

    # 获取用户身份（玩家6）
    user_role = next(p.role for p in game_state.players if p.id == 6)

    return {"game_id": game_id, "user_role": user_role.value}

@app.get("/game/playing/{game_id}")
async def playing(game_id: str):
    if game_id not in game_states:
        raise HTTPException(status_code=404, detail="Game not found")

    game_state = game_states[game_id]

    async def event_generator():
        while not game_state.game_over and game_state.day < 7 and game_state.step < 200:
            while game_state.events:
                event = game_state.get_event()
                if event.etype == "DISPLAY":
                    game_state.step += 1
                    yield sse_event({
                        "type": "display",
                        "content": event.content,
                        "day": game_state.day,
                        "phase": game_state.phase,
                        "alive": game_state.alive_players
                    })
                elif event.etype == "ALLOW_ACT":
                    game_state.step += 1
                    pid = event.target
                    player = game_state.players[pid - 1]
                    if pid == 6:
                        if player.role == Role.WEREWOLF:
                            tmp = [p.id for p in game_state.players if (p.role == Role.WEREWOLF) and (p.id != 6) and (p.id in game_state.alive_players)]
                            yield sse_event({
                                "type": "act",
                                "content": "请选择你的行动",
                                "day": game_state.day,
                                "phase": game_state.phase,
                                # 在前端用户可以执行的操作
                                "action": ["conversation", "kill"],
                                # "CONVERSATION"操作对应的玩家ID列表
                                "conversation": tmp,
                                # "KILL"操作对应的玩家ID列表，可以杀死自己
                                "kill": [i for i in game_state.alive_players if i not in tmp]
                            })
                        elif player.role == Role.WITCH:
                            info = {
                                "type": "act",
                                "content": "请选择你的行动",
                                "day": game_state.day,
                                "phase": game_state.phase,
                                # 在前端用户可以执行的操作
                                "action": ["resurrection", "kill", "none"],
                                # "RESURRECTION"操作对应的玩家ID列表
                                "resurrection": game_state.just_killed,
                                # "KILL"操作对应的玩家ID列表
                                "kill": [i for i in game_state.alive_players if i != 6],
                                # "NONE"操作对应的玩家ID列表
                                "none": []
                            }
                            if player.good_drup == 0:
                                del info["resurrection"]
                                info["action"].remove("resurrection")
                            if player.bad_drup == 0:
                                del info["kill"]
                                info["action"].remove("kill")
                            yield sse_event(info)
                        elif player.role == Role.SEER:
                            yield sse_event({
                                "type": "act",
                                "content": "请选择你的行动",
                                "day": game_state.day,
                                "phase": game_state.phase,
                                # 在前端用户可以执行的操作
                                "action": ["check"],
                                # "CHECK"操作对应的玩家ID列表
                                "check": [i for i in game_state.alive_players if i != 6]
                            })
                        game_events[game_id].clear()
                        await game_events[game_id].wait()
                    else:
                        if player.role == Role.WEREWOLF:
                            result = await agents["werewolf"].act(game_state, player, count=game_state.conversations)
                            if not result:
                                game_state.add_event(event)
                            else:
                                yield sse_event({
                                    "type": "display",
                                    "content": "狼人正在行动",
                                    "day": game_state.day,
                                    "phase": game_state.phase,
                                    "alive": game_state.alive_players
                                })

                                if result["action"] == "conversation":
                                    game_state.add_event(ConversationEvent(day=game_state.day, phase=game_state.phase,
                                                                           source=player.id, target=result["target"],
                                                                           content=result["content"],
                                                                           count=game_state.conversations))
                                else:
                                    game_state.add_event(KillEvent(day=game_state.day, phase=game_state.phase, reason=result["reason"],
                                                                   source=pid, target=result["target"]))
                        elif player.role == Role.WITCH:
                            result = await agents["witch"].act(game_state, player, game_state.just_killed[0])
                            if not result:
                                game_state.add_event(event)
                            else:
                                yield sse_event({
                                    "type": "display",
                                    "content": "女巫正在行动",
                                    "day": game_state.day,
                                    "phase": game_state.phase,
                                    "alive": game_state.alive_players
                                })
                                if result["action"] == "kill":
                                    game_state.add_event(KillEvent(day=game_state.day, phase=game_state.phase, reason=result["reason"],
                                                                   source=pid, target=result["target"]))
                                elif result["action"] == "resurrection":
                                    game_state.add_event(
                                        ResurrectionEvent(day=game_state.day, phase=game_state.phase, source=pid,
                                                          reason=result["reason"], target=result["target"]))
                                else:
                                    game_state.add_system_history(content=f"玩家{player.id}选择什么也不做。理由是：{result['reason']}")
                                    game_state.add_player_history(player.id, content=f"我选择什么也不做理由是：{result['reason']}")
                        elif player.role == Role.SEER:
                            result = await agents["seer"].act(game_state, player)
                            if not result:
                                game_state.add_event(event)
                            else:
                                yield sse_event({
                                    "type": "display",
                                    "content": "预言家正在行动",
                                    "day": game_state.day,
                                    "phase": game_state.phase,
                                    "alive": game_state.alive_players
                                })
                                game_state.add_event(CheckEvent(day=game_state.day, phase=game_state.phase, source=pid,
                                                                target=result["target"], reason=result["reason"]))
                elif event.etype == "CONVERSATION":
                    game_state.step += 1
                    sid = event.source
                    tid = event.target
                    player = game_state.players[tid - 1]
                    game_state.conversations += 1
                    game_state.add_system_history(content=f"玩家{sid}向玩家{tid}发送消息：{event.content}")
                    game_state.add_player_history(sid, content=f"我向玩家{tid}发送消息：{event.content}")
                    game_state.add_player_history(tid, content=f"玩家{sid}向我发送消息：{event.content}")
                    if tid == 6:
                        tmp = [p.id for p in game_state.players if (p.role == Role.WEREWOLF) and (p.id != 6) and (p.id in game_state.alive_players)]
                        yield sse_event({
                                "type": "conversation",
                                "content": f"玩家{sid}(你的队友)说：" + event.content + "\n请选择你的行动",
                                "day": game_state.day,
                                "phase": game_state.phase,
                                "source": sid,
                                # 在前端用户可以执行的操作
                                "action": ["conversation", "kill"] if tmp else ["kill"],
                                # "CONVERSATION"操作对应的玩家ID列表
                                "conversation": tmp,
                                # "KILL"操作对应的玩家ID列表
                                "kill": [i for i in game_state.alive_players if i not in tmp]
                        })
                        game_events[game_id].clear()
                        await game_events[game_id].wait()
                    else:
                        result = await agents["werewolf"].act(game_state, player, count=game_state.conversations)
                        if not result:
                            game_state.add_event(event)
                        else:
                            if result["action"] == "conversation":
                                game_state.add_event(
                                    ConversationEvent(day=game_state.day, phase=game_state.phase,
                                                      source=player.id, target=result["target"],
                                                      content=result["content"], count=game_state.conversations))
                            else:
                                game_state.add_event(KillEvent(day=game_state.day, phase=game_state.phase, reason=result["reason"],
                                                               source=tid, target=result["target"]))
                elif event.etype == "KILL":
                    game_state.step += 1
                    sid = event.source
                    splayer = game_state.players[sid - 1]
                    tid = event.target
                    if splayer.role == Role.WEREWOLF:
                        wid = [p.id for p in game_state.players if p.role == Role.WEREWOLF]
                        for e in game_state.events:
                            if isinstance(e, AllowActEvent) or isinstance(e, ConversationEvent) or isinstance(e,
                                                                                                              KillEvent):
                                if e.target in wid:
                                    game_state.events.remove(e)
                                    break
                    game_state.add_just_killed(tid, sid)
                    game_state.add_system_history(content=f"玩家{sid}杀死了玩家{tid},理由是：{event.reason}")
                    game_state.add_player_history(sid, content=f"我杀死了玩家{tid},理由是：{event.reason}")
                    if sid == 6:
                        yield sse_event({
                            "type": "display",
                            "content": f"你杀死了玩家{tid}",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            "alive": game_state.alive_players
                        })
                    if game_state.players[5].role == Role.WEREWOLF and sid != 6:
                        yield sse_event({
                            "type": "display",
                            "content": f"你的队友玩家{sid}杀死了玩家{tid}",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            "alive": game_state.alive_players
                        })

                elif event.etype == "RESURRECTION":
                    game_state.step += 1
                    sid = event.source
                    tid = event.target
                    game_state.resurrection(tid, sid)
                    game_state.add_system_history(content=f"玩家{sid}复活了玩家{tid},理由是：{event.reason}")
                    game_state.add_player_history(sid, content=f"我复活了玩家{tid},理由是：{event.reason}")
                    if sid == 6:
                        yield sse_event({
                            "type": "display",
                            "content": f"你复活了玩家{tid}",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            "alive": game_state.alive_players
                        })
                elif event.etype == "CHECK":
                    game_state.step += 1
                    sid = event.source
                    tid = event.target
                    tplayer = game_state.players[tid - 1]
                    m = {
                        Role.WEREWOLF: '狼人',
                        Role.WITCH: '女巫',
                        Role.SEER: '预言家',
                        Role.VILLAGER: '平民'
                    }

                    role = m[tplayer.role]
                    game_state.add_system_history(content=f"玩家{sid}检查了玩家{tid}的身份，玩家{tid}的身份为{role},理由是：{event.reason}")
                    game_state.add_player_history(sid, content=f"我检查了玩家{tid}的身份，玩家{tid}的身份为{role},理由是：{event.reason}")
                    if sid == 6:
                        yield sse_event({
                            "type": "display",
                            "content": f"玩家{tid}的身份是{role}",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            "alive": game_state.alive_players
                        })
                elif event.etype == "PHASE_CHANGE":
                    game_state.step += 1
                    game_state.phase = event.change
                    if game_state.phase == Phase.DAY:
                        game_state.kill_player()
                        game_state.when_day_event()
                        tmp = (' | '.join([f'玩家{i}' for i in game_state.just_killed]) + '被杀死了') \
                            if game_state.just_killed else '没有人死亡'

                        game_state.add_system_history(
                            content=f"现在是白天,昨晚{tmp}")
                        del tmp
                    elif game_state.phase == Phase.COUNT_VOTES:
                        game_state.set_out()
                        if game_state.check_game_over():
                            game_state.game_over = True
                            yield sse_event({
                                "type": "finish",
                                "winner": game_state.winner,
                                "game_over": True
                            })
                        game_state.when_count_vote_event()
                elif event.etype == "ALLOW_SPEAK":
                    game_state.step += 1
                    pid = event.target
                    player = game_state.players[pid - 1]
                    if player.id != 6:
                        # agent = agents.get(game_state.role_map.get(player.role))
                        agent = agents.get(player.role)
                        tmp = ""
                        mid = str(uuid.uuid4())
                        async for chunk in agent.speak(game_state, player):
                            tmp += chunk
                            yield sse_event({
                                "type": "speak",
                                "id": player.id,
                                "content": chunk,
                                "phase": game_state.phase,
                                "day": game_state.day,
                                "mid": mid
                            })
                        del mid
                        game_state.add_system_history(content=f"玩家{pid}发言：{tmp}")
                        game_state.add_player_history(pid, content=f"我的发言：{tmp}")
                    else:
                        yield sse_event({
                            "type": "user_speak",
                            "content": "开始你的发言",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            # 在前端用户可以执行的操作
                            "action": ["speak"],
                            "alive": game_state.alive_players
                        })
                        game_events[game_id].clear()
                        await game_events[game_id].wait()
                elif event.etype == "ALLOW_VOTE":
                    game_state.step += 1
                    pid = event.target
                    player = game_state.players[pid - 1]
                    if pid == 6:
                        yield sse_event({
                            "type": "voting",
                            "content": "请进行投票",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            # 在前端用户可以执行的操作
                            "action": ["voting"],
                            # "VOTING"操作对应的玩家ID列表
                            "voting": game_state.alive_players,
                            "alive": game_state.alive_players
                        })
                        game_events[game_id].clear()
                        await game_events[game_id].wait()
                    else:
                        agent = agents.get(player.role)
                        result = await agent.vote(game_state, player)
                        if not result:
                            game_state.add_event(event)
                        else:
                            if result["action"] == "vote":
                                game_state.add_event(
                                    VoteEvent(day=game_state.day, phase=game_state.phase, reason=result["reason"],
                                              source=player.id, target=result["target"]))
                elif event.etype == "VOTE":
                    game_state.step += 1
                    sid = event.source
                    tid = event.target
                    game_state.vote(tid)
                    game_state.add_system_history(content=f"玩家{sid}投票给了玩家{tid},理由是：{event.reason}")
                    game_state.add_player_history(sid, content=f"我投票给了玩家{tid},理由是：{event.reason}")
                    if sid == 6:
                        yield sse_event({
                            "type": "display",
                            "content": f"你投票给了玩家{tid}",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            "alive": game_state.alive_players
                        })
                    else:
                        yield sse_event({
                            "type": "display",
                            "content": f"玩家{sid}投票给了玩家{tid}",
                            "day": game_state.day,
                            "phase": game_state.phase,
                            "alive": game_state.alive_players
                        })
                elif event.etype == "DAY_CHANGE":
                    game_state.next_day()

                continue

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@app.post("/game/send/{game_id}")
async def send(game_id: str, event: Dict[str, Any]):
    if game_id not in game_states:
        raise HTTPException(status_code=404, detail="Game not found")

    game_state = game_states[game_id]
    print(event)

    if event["etype"] == "NONE":
        game_state.add_system_history(content="玩家6什么也没有做")
        game_state.add_player_history(6, content="我什么也没有做")
    elif event["etype"] == "SPEAK":
        game_state.add_system_history(f"玩家6说：{event['content']}")
        game_state.add_player_history(6, content=f"我说：{event['content']}")
    else:
        try:
            # 根据事件类型创建对应的事件对象
            event_map = {
                "CONVERSATION": ConversationEvent,
                "RESURRECTION": ResurrectionEvent,
                "KILL": KillEvent,
                "CHECK": CheckEvent,
                "VOTE": VoteEvent
            }

            if event["etype"] not in event_map:
                raise HTTPException(status_code=400, detail=f"Invalid event type: {event['etype']}")

            # 转换为具体的事件类型并验证
            if event["etype"] == "CONVERSATION":
                specific_event = event_map[event["etype"]](**event, day=game_state.day, phase=game_state.phase, count=game_state.conversations)
            else:
                specific_event = event_map[event["etype"]](**event, day=game_state.day, phase=game_state.phase)

            # 将事件添加到游戏状态
            game_states[game_id].add_event(specific_event)

        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid event data: {str(e)}")
    game_events[game_id].set()
    return {"status": "success"}


@app.get("/game/end/{game_id}")
async def end_game(game_id: str):
    """结束游戏"""
    if game_id not in game_states:
        raise HTTPException(status_code=404, detail="Game not found")

    game_state = game_states[game_id]
    game_state.game_over = True

    return {"status": "success"}


@app.get("/game/reset/{game_id}")
async def reset_game(game_id: str):
    """重置游戏"""
    if game_id not in game_states:
        raise HTTPException(status_code=404, detail="Game not found")

    game_state = GameState()
    game_state.initialize_players()
    game_states[game_id] = game_state
    game_events[game_id].clear()

    user_role = next(p.role for p in game_state.players if p.id == 6)

    return {"status": "success", "user_role": user_role.value}


@app.get("/game/review/{game_id}")
async def game_review(game_id: str):
    """获取游戏复盘"""
    if game_id not in game_states:
        raise HTTPException(status_code=404, detail="Game not found")

    game_state = game_states[game_id]
    return {"events": [e.dict() for e in game_state.histories[0]]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app="main:app", host="127.0.0.1", port=8000, reload=True)
