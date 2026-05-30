import argparse
import json
import os

try:
    from .embeddingData import embeddingData
except ImportError:
    from embeddingData import embeddingData


class queryData:
    def __init__(self, elasticsearch_url=None):
        try:
            from elasticsearch import Elasticsearch
        except ImportError as exc:
            raise RuntimeError("缺少 elasticsearch 依赖，请先安装 requirements.txt") from exc

        self.es = Elasticsearch(hosts=[elasticsearch_url or os.environ.get("ELASTICSEARCH_URL")])

    def keyword_query(self, index_name, query_text, top_k=10):
        query_body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": [
                        "movie_title^4",
                        "director^3",
                        "actors^3",
                        "genre.text^2",
                        "tags^2",
                        "summary^2",
                        "script",
                    ],
                    "type": "best_fields",
                }
            },
        }
        return self.es.search(index=index_name, body=query_body)

    def vector_query(self, index_name, query_text, top_k=10, vector_field="embedding_script"):
        embedding_vector = embeddingData().get_embedding(query_text)
        query_body = {
            "size": top_k,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": f"cosineSimilarity(params.query_vector, '{vector_field}') + 1.0",
                        "params": {"query_vector": embedding_vector},
                    },
                }
            },
        }
        return self.es.search(index=index_name, body=query_body)

    def hybrid_query(
        self,
        index_name,
        query_text,
        top_k=5,
        recall_k=20,
        rrf_k=60,
        vector_field="embedding_script",
    ):
        keyword_response = self.keyword_query(index_name, query_text, top_k=recall_k)
        vector_response = self.vector_query(index_name, query_text, top_k=recall_k, vector_field=vector_field)

        merged = {}
        self._merge_rrf(merged, keyword_response["hits"]["hits"], "keyword", rrf_k)
        self._merge_rrf(merged, vector_response["hits"]["hits"], "vector", rrf_k)

        results = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def _merge_rrf(self, merged, hits, source_name, rrf_k):
        for rank, hit in enumerate(hits, start=1):
            doc_id = hit["_id"]
            if doc_id not in merged:
                merged[doc_id] = {
                    "id": doc_id,
                    "score": 0.0,
                    "sources": [],
                    "source": hit["_source"],
                    "raw_scores": {},
                    "ranks": {},
                }

            merged[doc_id]["score"] += 1.0 / (rrf_k + rank)
            merged[doc_id]["sources"].append(source_name)
            merged[doc_id]["raw_scores"][source_name] = hit.get("_score")
            merged[doc_id]["ranks"][source_name] = rank


def simplify_results(results):
    simplified = []
    for item in results:
        source = item["source"]
        simplified.append(
            {
                "id": item["id"],
                "rrf_score": round(item["score"], 6),
                "sources": item["sources"],
                "ranks": item["ranks"],
                "movie_title": source.get("movie_title"),
                "segment_index": source.get("segment_index"),
                "summary": source.get("summary"),
                "script": source.get("script", "")[:300],
            }
        )
    return simplified


def run_search(query, mode="hybrid", index_name="movies", top_k=5, recall_k=20, vector_field="embedding_script"):
    qd = queryData()
    if mode == "keyword":
        response = qd.keyword_query(index_name, query, top_k=top_k)
        results = [
            {
                "id": hit["_id"],
                "score": hit["_score"],
                "sources": ["keyword"],
                "source": hit["_source"],
                "ranks": {},
            }
            for hit in response["hits"]["hits"]
        ]
    elif mode == "vector":
        response = qd.vector_query(index_name, query, top_k=top_k, vector_field=vector_field)
        results = [
            {
                "id": hit["_id"],
                "score": hit["_score"],
                "sources": ["vector"],
                "source": hit["_source"],
                "ranks": {},
            }
            for hit in response["hits"]["hits"]
        ]
    else:
        results = qd.hybrid_query(
            index_name,
            query,
            top_k=top_k,
            recall_k=recall_k,
            vector_field=vector_field,
        )

    return simplify_results(results)


def main():
    parser = argparse.ArgumentParser(description="Run Elasticsearch movie search.")
    parser.add_argument("query", help="搜索问题，例如：梦境和现实")
    parser.add_argument("--index", default="movies", help="ES 索引名")
    parser.add_argument("--mode", choices=["keyword", "vector", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5, help="最终返回数量")
    parser.add_argument("--recall-k", type=int, default=20, help="混合检索每路召回数量")
    parser.add_argument(
        "--vector-field",
        choices=["embedding_script", "embedding_summary"],
        default="embedding_script",
        help="向量检索使用的字段",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    results = run_search(
        args.query,
        mode=args.mode,
        index_name=args.index,
        top_k=args.top_k,
        recall_k=args.recall_k,
        vector_field=args.vector_field,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for index, item in enumerate(results, start=1):
            print(f"\n#{index} {item['movie_title']} segment {item['segment_index']}")
            print(f"id: {item['id']}")
            print(f"rrf_score: {item['rrf_score']}")
            print(f"sources: {', '.join(item['sources'])}")
            print(f"ranks: {item['ranks']}")
            print(f"summary: {item['summary']}")
            print(f"script: {item['script']}")


if __name__ == "__main__":
    main()
