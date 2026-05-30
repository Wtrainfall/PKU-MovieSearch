from config.qwen import build_qwen_client, get_qwen_chat_model


SUMMARY_SYSTEM_PROMPT = (
    "你是一个电影剧本摘要生成器，专注于提取剧本片段的主要情节、场景、"
    "关键信息和重要人物，并生成简练的摘要。"
)

SUMMARY_PROMPT_TEMPLATE = """
请为以下电影剧本片段生成一个简要的摘要。

要求：
1、提取片段中的主要情节、场景、关键信息和重要人物，突出故事的核心内容。
2、摘要必须简练，长度不超过300字。
3、使用中文回答，只需要回答摘要内容，不需其他解释或说明。
4、无需分点作答，直接给出连贯的摘要文本。

片段内容：
{content}

请为以上片段生成一个符合要求的摘要。
"""


class getSummary:
    def __init__(self):
        self.client = build_qwen_client()
        self.model = get_qwen_chat_model('QWEN_SUMMARY_MODEL')

    def get_summary(self, string):
        prompt = SUMMARY_PROMPT_TEMPLATE.format(content=string)

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': SUMMARY_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ],
        )

        return completion.choices[0].message.content
