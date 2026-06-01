import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods

from .agent import movie_search_agent


JSON_DUMPS_PARAMS = {'ensure_ascii': False}


def _sse_event(name, payload):
    body = json.dumps(payload, ensure_ascii=False)
    return f'event: {name}\ndata: {body}\n\n'


def _stream_agent_events(question, thread_id):
    stream = movie_search_agent.stream(question, thread_id=thread_id)
    answer_started = False
    final_payload = None

    yield _sse_event('status', {'stage': 'start', 'message': '开始分析问题'})

    for event in stream:
        event_type = event.get('event')
        payload = event.get('payload', {})

        if event_type == 'subagent_start':
            yield _sse_event('subagent_start', payload)
        elif event_type == 'subagent_result':
            yield _sse_event('process', payload)
        elif event_type == 'answer_token':
            if not answer_started:
                answer_started = True
                yield _sse_event('status', {'stage': 'answer', 'message': '开始生成回答'})
            yield _sse_event('answer_token', payload)
        elif event_type == 'final':
            final_payload = payload
        elif event_type == 'error':
            yield _sse_event('error', payload)
            return

    if final_payload is not None:
        yield _sse_event('final', final_payload)
    yield _sse_event('done', {'ok': True})


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
            'process_trace': result.get('process_trace', {}),
        },
        json_dumps_params=JSON_DUMPS_PARAMS,
    )


@require_http_methods(['GET', 'POST'])
def agent_stream_api(request):
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
    else:
        question = request.GET.get('q', '').strip()
        thread_id = request.GET.get('thread_id', 'default').strip() or 'default'

    if not question:
        return JsonResponse(
            {'error': '缺少查询问题 q 或 question'},
            status=400,
            json_dumps_params=JSON_DUMPS_PARAMS,
        )

    response = StreamingHttpResponse(
        _stream_agent_events(question, thread_id),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
