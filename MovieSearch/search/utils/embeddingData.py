import os
from openai import OpenAI

class embeddingData:
    def __init__(self):

        self.client = OpenAI(
            api_key=os.environ.get('ALI_API_KEY'),
            base_url=os.environ.get('ALI_API_URL')
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