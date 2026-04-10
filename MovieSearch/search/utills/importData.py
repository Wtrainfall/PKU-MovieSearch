from elasticsearch import Elasticsearch

class importData:
    def __init__(self, content, target_index):
        self.es = Elasticsearch(["http://localhost:9200"])
        self.content = content
        self.target_index = target_index

    def import_data(self):
        doc_id = f"{self.content['movie_id']}_{self.content['segment_index']}"
        if not self.es.exists(index=self.target_index, id=doc_id):
            self.es.index(index=self.target_index, id=doc_id, body=self.content)
            print(f"Document with ID {doc_id} imported into index {self.target_index}.")
        else:
            print(f"Document with ID {doc_id} already exists in index {self.target_index}. Skipping import.")
