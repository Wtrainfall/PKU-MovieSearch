from config.qwen import build_qwen_chat_model

def build_chat_model():
    return build_qwen_chat_model(model_env='QWEN_AGENT_MODEL', temperature=0)
