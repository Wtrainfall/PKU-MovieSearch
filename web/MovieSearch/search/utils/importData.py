from elasticsearch import Elasticsearch
import os

class importData:
    def __init__(self):
        self.es = Elasticsearch([os.environ.get('ELASTICSEARCH_URL')])

    def import_data(self, content, target_index):
        doc_id = f"{content['movie_id']}_{content['segment_index']}"
        if not self.es.exists(index=target_index, id=doc_id):
            self.es.index(index=target_index, id=doc_id, body=content)
            print(f"Document with ID {doc_id} imported into index {target_index}.")
        else:
            print(f"Document with ID {doc_id} already exists in index {target_index}. Skipping import.")
