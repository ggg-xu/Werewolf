# Werewolf

一个多智能体狼人杀游戏

## 搭建环境

```sh
# 进入项目目录
cd /Werewolf
#同步依赖
uv sync

#输出虚拟环境的绝对路径，确定环境已安装
uv venv --show
```

## 配置LLM

```toml
#config.toml
[llm]
model="your_model"
base_url="your_base_url"
api_key="your_api_key"
temperature=0.5
```

## 启动游戏

```sh
cd /Werewolf/backend/
python main.py
```

## 开始游戏

http://127.0.0.1:8000/index
