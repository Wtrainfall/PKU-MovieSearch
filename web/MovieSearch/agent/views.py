import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .agent import movie_search_agent


JSON_DUMPS_PARAMS = {'ensure_ascii': False}


@require_http_methods(['GET', 'POST'])
def agent_api(request):
    thread_id = 'default'
    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': '请求体必须是 JSON'},
                status=400,
                json_dumps_params=JSON_DUMPS_PARAMS,
            )

        question = str(payload.get('question') or payload.get('q') or '').strip()
        thread_id = str(payload.get('thread_id') or 'default').strip() or 'default'
        top_k_value = payload.get('top_k', 5)
    else:
        question = request.GET.get('q', '').strip()
        thread_id = request.GET.get('thread_id', 'default').strip() or 'default'
        top_k_value = request.GET.get('top_k', 5)

    if not question:
        return JsonResponse(
            {'error': '缺少查询问题 q 或 question'},
            status=400,
            json_dumps_params=JSON_DUMPS_PARAMS,
        )

    try:
        top_k = int(top_k_value)
    except ValueError:
        return JsonResponse(
            {'error': 'top_k 必须是整数'},
            status=400,
            json_dumps_params=JSON_DUMPS_PARAMS,
        )

    if top_k < 1 or top_k > 10:
        return JsonResponse(
            {'error': 'agent top_k 必须在 1 到 10 之间'},
            status=400,
            json_dumps_params=JSON_DUMPS_PARAMS,
        )

    try:
        result = movie_search_agent.ask(question, max_results=top_k, thread_id=thread_id)
    except Exception as exc:
        return JsonResponse(
            {'error': 'agent 调用失败', 'detail': str(exc)},
            status=500,
            json_dumps_params=JSON_DUMPS_PARAMS,
        )

    return JsonResponse(
        {
            'thread_id': thread_id,
            'query': question,
            'answer': result['answer'],
            'evidence': result['evidence'],
            'clue_state': result.get('clue_state', {}),
            'candidate_review': result.get('candidate_review', {}),
        },
        json_dumps_params=JSON_DUMPS_PARAMS,
    )
