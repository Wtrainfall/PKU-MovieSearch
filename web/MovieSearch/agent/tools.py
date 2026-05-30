from contextvars import ContextVar

from search.utils.queryData import run_search


_search_events = ContextVar("movie_search_events", default=None)


def start_search_trace():
    return _search_events.set([])


def stop_search_trace(token):
    events = _search_events.get() or []
    _search_events.reset(token)
    return events


def movie_hybrid_search(query: str, max_results: int = 5):
    """Search movie script segments with hybrid keyword and semantic retrieval."""
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
    events = _search_events.get()
    if events is not None:
        events.append(payload)
    return payload
