from config.qwen import build_qwen_client, get_qwen_embedding_model


class embeddingData:
    def __init__(self):
        self.client = build_qwen_client()
        self.model = get_qwen_embedding_model()

    def get_embedding(self, string):
        completion = self.client.embeddings.create(
            model=self.model,
            input=string,
            dimensions=768,
            encoding_format='float',
        )
        embedding = completion.data[0].embedding
        return embedding
