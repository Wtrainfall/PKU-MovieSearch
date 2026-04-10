from elasticsearch import Elasticsearch

index = {
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

es = Elasticsearch(hosts=["http://localhost:9200"])
index_name = "movies"

if es.indices.exists(index=index_name):
    es.indices.delete(index=index_name)
    es.indices.create(index=index_name, **index)
else:
    es.indices.create(index=index_name, **index)

print("Index created successfully.")
