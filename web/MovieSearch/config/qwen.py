import os

from langchain_openai import ChatOpenAI
from openai import OpenAI


DEFAULT_QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
DEFAULT_QWEN_CHAT_MODEL = 'qwen-plus'
DEFAULT_QWEN_EMBEDDING_MODEL = 'text-embedding-v3'


def _env(name):
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def require_env(name):
    value = _env(name)
    if not value:
        raise RuntimeError(f'缺少环境变量: {name}')
    return value


def get_qwen_api_key():
    return require_env('QWEN_API_KEY')


def get_qwen_base_url():
    return _env('QWEN_BASE_URL') or DEFAULT_QWEN_BASE_URL


def get_qwen_chat_model(model_env=None):
    if model_env:
        model = _env(model_env)
        if model:
            return model
    return _env('QWEN_CHAT_MODEL') or DEFAULT_QWEN_CHAT_MODEL


def get_qwen_embedding_model():
    return _env('QWEN_EMBEDDING_MODEL') or DEFAULT_QWEN_EMBEDDING_MODEL


def build_qwen_client():
    return OpenAI(
        api_key=get_qwen_api_key(),
        base_url=get_qwen_base_url(),
    )


def build_qwen_chat_model(model_env=None, temperature=0):
    return ChatOpenAI(
        model=get_qwen_chat_model(model_env),
        api_key=get_qwen_api_key(),
        base_url=get_qwen_base_url(),
        temperature=temperature,
    )
