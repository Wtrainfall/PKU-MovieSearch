import os

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from search.utils.queryData import run_search


JSON_DUMPS_PARAMS = {'ensure_ascii': False}


def _error_response(message, status, detail=None):
    payload = {'error': message}
    if detail is not None:
        payload['detail'] = detail
    return JsonResponse(payload, status=status, json_dumps_params=JSON_DUMPS_PARAMS)


@require_GET
def search_api(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return _error_response('缺少查询参数 q', status=400)

    mode = request.GET.get('mode', 'hybrid')
    if mode not in {'keyword', 'vector', 'hybrid'}:
        return _error_response('mode 只能是 keyword、vector 或 hybrid', status=400)

    vector_field = request.GET.get('vector_field', 'embedding_script')
    if vector_field not in {'embedding_script', 'embedding_summary'}:
        return _error_response(
            'vector_field 只能是 embedding_script 或 embedding_summary',
            status=400,
        )

    try:
        top_k = int(request.GET.get('top_k', 5))
        recall_k = int(request.GET.get('recall_k', 20))
    except ValueError:
        return _error_response('top_k 和 recall_k 必须是整数', status=400)

    if top_k < 1 or top_k > 50:
        return _error_response('top_k 必须在 1 到 50 之间', status=400)
    if recall_k < top_k or recall_k > 200:
        return _error_response('recall_k 必须大于等于 top_k，且不超过 200', status=400)

    try:
        results = run_search(
            query,
            mode=mode,
            top_k=top_k,
            recall_k=recall_k,
            vector_field=vector_field,
        )
    except Exception as exc:
        return _error_response('搜索失败', status=500, detail=str(exc))

    return JsonResponse(
        {
            'query': query,
            'mode': mode,
            'top_k': top_k,
            'recall_k': recall_k,
            'vector_field': vector_field,
            'results': results,
        },
        json_dumps_params=JSON_DUMPS_PARAMS,
    )


@require_GET
def stats_api(request):
    try:
        from elasticsearch import Elasticsearch

        es = Elasticsearch(hosts=[os.environ.get('ELASTICSEARCH_URL')])
        index_name = request.GET.get('index', 'movies')

        segment_count = es.count(index=index_name)['count']
        response = es.search(
            index=index_name,
            size=0,
            body={
                'aggs': {
                    'movie_count': {
                        'cardinality': {
                            'field': 'movie_id',
                        }
                    }
                }
            },
        )
        movie_count = response['aggregations']['movie_count']['value']
    except Exception as exc:
        return _error_response('统计失败', status=500, detail=str(exc))

    return JsonResponse(
        {
            'index': index_name,
            'movie_count': movie_count,
            'segment_count': segment_count,
        },
        json_dumps_params=JSON_DUMPS_PARAMS,
    )

