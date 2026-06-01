import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone

from search.utils.queryData import run_search


_search_events = ContextVar("movie_search_events", default=None)
logger = logging.getLogger(__name__)


def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def _log_agent_event(event, **payload):
    logger.info(
        'agent_event %s',
        json.dumps(
            {
                'event': event,
                'timestamp': _utc_timestamp(),
                **payload,
            },
            ensure_ascii=False,
            default=str,
        ),
    )


def start_search_trace():
    return _search_events.set([])


def stop_search_trace(token):
    events = _search_events.get() or []
    _search_events.reset(token)
    return events


def movie_hybrid_search(query: str, max_results: int = 3):
    """Search movie script segments with hybrid keyword and semantic retrieval."""
    start_time = time.perf_counter()
    _log_agent_event(
        'tool.movie_hybrid_search.start',
        query_length=len(query or ''),
        max_results=max_results,
    )
    payload = {
        "query": query,
        "results": run_search(
            query,
            mode="hybrid",
            top_k=max_results,
            recall_k=max(30, max_results * 5),
            vector_field="embedding_summary",
        ),
    }
    _log_agent_event(
        'tool.movie_hybrid_search.end',
        query_length=len(query or ''),
        max_results=max_results,
        result_count=len(payload["results"]),
        duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
    )
    events = _search_events.get()
    if events is not None:
        events.append(payload)
    return payload
