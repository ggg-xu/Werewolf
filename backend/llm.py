from langchain_openai.chat_models import ChatOpenAI
import toml
from pathlib import Path

CONFIG = Path(__file__).parent.parent / 'config.toml'

llm_config = toml.load(CONFIG)['llm']

llm = ChatOpenAI(
    openai_api_key=llm_config['api_key'],
    model=llm_config['model'],
    base_url=llm_config['base_url'],
    temperature=llm_config['temperature']
)
