from elasticsearch import Elasticsearch
from embeddingData import embeddingData
import os

class queryData:
    def __init__(self):
        self.es = Elasticsearch(hosts=[os.environ.get('ELASTICSEARCH_URL'])

    def natural_language_query(self, index_name, query_text, top_k=5):
        embedding = embeddingData()
        embedding_vector = embedding.get_embedding(query_text)
        query_body = {
            "size": top_k,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding_script') + 1.0",
                        "params": {"query_vector": embedding_vector}
                    }
                }
            }
        }
        response = self.es.search(index=index_name, body=query_body)

        return response
    
    def keyword_query(self, index_name, query_text, top_k=5):
        query_body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": ["movie_title^3", "genre^2", "director^2", "actors^2", "tags", "summary" ]
                }
            }
        }
        response = self.es.search(index=index_name, body=query_body)

        return response
        
    

if __name__ == '__main__':
    qd = queryData()
    response = qd.keyword_query(index_name='movies', query_text='诺兰')
    for hit in response['hits']['hits']:
        print(hit['_source']['movie_title'])

