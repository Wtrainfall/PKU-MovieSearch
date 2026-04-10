from openai import OpenAI

class embeddingData:
    def __init__(self):

        self.client = OpenAI(
            api_key="sk-07463790df7241679d3489b7e5902eab",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    
    def get_embedding(self, string):
        completion = self.client.embeddings.create(
            model='text-embedding-v3',
            input= string,
            dimensions=768,
            encoding_format='float'
        )
        embedding = completion.data[0].embedding
        return embedding

if __name__ == '__main__':
    EmbeddingData = embeddingData().get_embedding("hello world")
    print(EmbeddingData)