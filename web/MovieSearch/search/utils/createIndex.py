from elasticsearch import Elasticsearch
import os

class createIndex:

  def __init__(self):
    self.es =  Elasticsearch(hosts=[os.environ.get('ELASTICSEARCH_URL')])
    self.index_name = "movies"
    self.index = {
              "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
              },
              "mappings": {
                "properties": {
                  "movie_id": {
                    "type": "keyword"
                  },
                  "movie_title": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "fields": {
                      "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                      },
                      "suggest": {
                        "type": "completion"
                      }
                    }
                  },
                  "segment_index": {
                    "type": "integer"
                  },
                  "genre": {
                    "type": "keyword",
                    "fields": {
                      "text": {
                        "type": "text",
                        "analyzer": "ik_max_word"
                      }
                    }
                  },
                  "year": {
                    "type": "integer"
                  },
                  "director": {
                    "type": "keyword"
                  },
                  "actors": {
                    "type": "keyword",
                    "fields": {
                      "text": {
                        "type": "text",
                        "analyzer": "ik_max_word"
                      }
                    }
                  },
                  "tags": {
                    "type": "keyword"
                  },
                  "script": {
                    "type": "text",
                    "analyzer": "ik_smart"
                  },
                  "summary": {
                    "type": "text",
                    "analyzer": "ik_smart"
                  },
                  "embedding_summary": {
                    "type": "dense_vector",
                    "dims": 768
                  },
                  "embedding_script": {
                    "type": "dense_vector",
                    "dims": 768
                  }
                }
              }
            }
            
  def create_index(self):
    if self.es.indices.exists(index=self.index_name):
      self.es.indices.delete(index=self.index_name)
      self.es.indices.create(index=self.index_name, body=self.index)
    else:
      self.es.indices.create(index=self.index_name, body=self.index)



