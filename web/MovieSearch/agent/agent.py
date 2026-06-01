import json
import logging
import re
import time
from contextvars import ContextVar
from datetime import datetime, timezone

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

from .llm import build_chat_model
from .tools import movie_hybrid_search, start_search_trace, stop_search_trace


_stream_task_calls = ContextVar('agent_stream_task_calls', default=None)
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


SYSTEM_PROMPT = """你是 MovieTOMT DeepAgent，负责帮用户找想不起名字的电影。

只基于检索 evidence 和子 Agent 结果回答，不编造。

调用策略：
1. 非找电影请求：直接简短回答，不调用子 Agent。
2. clue_extractor：仅在用户给新线索、修正线索、否认候选，或多轮上下文需要整理时调用；解释已有结果时不要调用。
3. movie_retriever：仅在线索足够且需要新候选时调用；主 Agent 不直接检索。
4. candidate_verifier：仅在有新候选且需要匹配判断时调用。
5. 每轮每个子 Agent 最多调用一次。

回答风格：
- 优先 1-3 句话。
- 不确定就追问一个最关键问题。
- 有可信候选时给片名、简短依据和 evidence。
"""


class ClueAnalysis(BaseModel):
    confirmed_clues: list[str] = Field(default_factory=list)
    uncertain_clues: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    negative_feedback: list[str] = Field(default_factory=list)
    enough_for_search: bool = False
    followup_question: str = ''
    rationale: str = ''


class RetrievalCandidate(BaseModel):
    movie_title: str
    segment_index: int | None = None
    evidence_id: str = ''
    summary: str = ''
    relevance: str = ''


class RetrievalStep(BaseModel):
    search_queries: list[str] = Field(default_factory=list)
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    retrieval_summary: str = ''
    gap_analysis: str = ''


class CandidateReviewItem(BaseModel):
    movie_title: str
    segment_index: int | None = None
    confidence: str
    matched_clues: list[str] = Field(default_factory=list)
    missing_clues: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class CandidateReview(BaseModel):
    candidates: list[CandidateReviewItem] = Field(default_factory=list)
    should_ask_followup: bool = False
    followup_question: str = ''
    review_summary: str = ''


CLUE_ANALYSIS_SCHEMA = json.dumps(ClueAnalysis.model_json_schema(), ensure_ascii=False, indent=2)
RETRIEVAL_STEP_SCHEMA = json.dumps(RetrievalStep.model_json_schema(), ensure_ascii=False, indent=2)
CANDIDATE_REVIEW_SCHEMA = json.dumps(CandidateReview.model_json_schema(), ensure_ascii=False, indent=2)


SUBAGENTS = [
    {
        'name': 'clue_extractor',
        'description': '从用户消息和对话历史中提取结构化电影线索，判断线索是否足够检索，适合在找电影、补充线索、否认候选或修正描述时调用。',
        'system_prompt': """你是电影线索整理子 Agent。

从当前消息、对话历史和上一轮候选中整理完整线索状态：
- confirmed_clues：确定线索
- uncertain_clues：不确定线索
- exclusions：排除片名
- negative_feedback：用户否认
- enough_for_search：是否足够检索
- followup_question：线索不足时只给一个关键追问
- rationale：一句话说明

只输出符合 schema 的 JSON，不要 Markdown，不要编造。

输出 JSON 必须符合以下 schema：
{CLUE_ANALYSIS_SCHEMA}
""".format(CLUE_ANALYSIS_SCHEMA=CLUE_ANALYSIS_SCHEMA),
        'tools': [],
    },
    {
        'name': 'movie_retriever',
        'description': '根据已整理的电影线索设计检索表达，并调用 movie_hybrid_search 获取候选电影片段。',
        'system_prompt': """你是电影检索子 Agent。

把线索改写成适合混合检索的 query，保留人物、情节、场景、关系、年代/地区。
最多调用 2 次检索；第一次结果可用时不要追加检索。
返回实际执行的 query、候选、摘要、相关性、检索总结和缺口。
只输出符合 schema 的 JSON，不要 Markdown。

输出 JSON 必须符合以下 schema：
{RETRIEVAL_STEP_SCHEMA}
""".format(RETRIEVAL_STEP_SCHEMA=RETRIEVAL_STEP_SCHEMA),
        'tools': [movie_hybrid_search],
    },
    {
        'name': 'candidate_verifier',
        'description': '对照用户线索验证候选电影和片段是否匹配，识别缺失线索、冲突线索和置信度，适合在已有候选 evidence 后调用。',
        'system_prompt': """你是候选验证子 Agent。

只依据候选片段验证匹配度。
对每个候选给出 high / medium / low、matched_clues、missing_clues、conflicts。
没有高置信候选时，只给一个最值得追问的问题。
只输出符合 schema 的 JSON，不要 Markdown，不要凭常识补全。

输出 JSON 必须符合以下 schema：
{CANDIDATE_REVIEW_SCHEMA}
""".format(CANDIDATE_REVIEW_SCHEMA=CANDIDATE_REVIEW_SCHEMA),
        'tools': [],
    },
]


class MovieSearchAgent:
    def __init__(self):
        self.checkpointer = InMemorySaver()
        self.thread_states = {}
        self.agent = None

    def _get_agent(self):
        if self.agent is None:
            start_time = time.perf_counter()
            _log_agent_event('agent.init.start')
            self.agent = create_deep_agent(
                model=build_chat_model(),
                tools=[],
                subagents=SUBAGENTS,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=self.checkpointer,
            )
            _log_agent_event('agent.init.end', duration_ms=self._elapsed_ms(start_time))
        return self.agent

    def ask(self, question, max_results=5, thread_id=None):
        thread_id = thread_id or 'default'
        start_time = time.perf_counter()
        clue_state = self._begin_clue_state_turn(thread_id)
        prompt = self._build_turn_prompt(question, clue_state)
        _log_agent_event(
            'agent.ask.start',
            thread_id=thread_id,
            question_length=len(question or ''),
            max_results=max_results,
            turn_count=clue_state.get('turn_count'),
        )
        token = start_search_trace()
        try:
            invoke_start = time.perf_counter()
            result = self._get_agent().invoke(
                {'messages': [{'role': 'user', 'content': prompt}]},
                config={'configurable': {'thread_id': thread_id}},
            )
            _log_agent_event('agent.ask.invoke.end', thread_id=thread_id, duration_ms=self._elapsed_ms(invoke_start))
            search_events = stop_search_trace(token)
        except Exception as exc:
            stop_search_trace(token)
            _log_agent_event(
                'agent.ask.error',
                thread_id=thread_id,
                duration_ms=self._elapsed_ms(start_time),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise

        process_trace = self._extract_process_trace(result.get('messages', []))
        self._sync_clue_state(clue_state, process_trace)
        evidence = self._extract_evidence_from_search_events(search_events, max_results, clue_state)
        self._set_last_candidates(clue_state, evidence)
        candidate_review = self._resolve_candidate_review(process_trace, evidence, clue_state)
        self._log_turn_summary(
            'agent.ask.end',
            thread_id,
            start_time,
            search_events,
            evidence,
            process_trace,
            candidate_review,
        )

        return {
            'answer': result['messages'][-1].content,
            'evidence': evidence,
            'clue_state': clue_state,
            'candidate_review': candidate_review,
            'process_trace': process_trace,
        }

    def stream(self, question, thread_id=None, max_results=5):
        thread_id = thread_id or 'default'
        start_time = time.perf_counter()
        clue_state = self._begin_clue_state_turn(thread_id)
        process_trace = {
            'clue_steps': [],
            'retrieval_steps': [],
            'candidate_steps': [],
        }
        prompt = self._build_turn_prompt(question, clue_state)
        search_token = start_search_trace()
        task_token = _stream_task_calls.set({})
        collected_answer_parts = []
        _log_agent_event(
            'agent.stream.start',
            thread_id=thread_id,
            question_length=len(question or ''),
            max_results=max_results,
            turn_count=clue_state.get('turn_count'),
        )

        try:
            stream_start = time.perf_counter()
            stream = self._get_agent().stream(
                {'messages': [{'role': 'user', 'content': prompt}]},
                config={'configurable': {'thread_id': thread_id}},
                stream_mode=['tasks', 'updates', 'messages'],
                subgraphs=True,
            )
            for event in stream:
                translated = self._translate_stream_event(event, collected_answer_parts)
                if translated is None:
                    continue
                self._log_stream_event(thread_id, translated, stream_start)
                if translated['event'] == 'subagent_result':
                    self._append_process_step(process_trace, translated['payload'])
                yield translated
        except Exception as exc:
            stop_search_trace(search_token)
            _stream_task_calls.reset(task_token)
            _log_agent_event(
                'agent.stream.error',
                thread_id=thread_id,
                duration_ms=self._elapsed_ms(start_time),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            yield {'event': 'error', 'payload': {'detail': str(exc)}}
            return

        search_events = stop_search_trace(search_token)
        _stream_task_calls.reset(task_token)

        self._sync_clue_state(clue_state, process_trace)
        evidence = self._extract_evidence_from_search_events(search_events, max_results, clue_state)
        self._set_last_candidates(clue_state, evidence)
        candidate_review = self._resolve_candidate_review(process_trace, evidence, clue_state)
        self._log_turn_summary(
            'agent.stream.end',
            thread_id,
            start_time,
            search_events,
            evidence,
            process_trace,
            candidate_review,
            answer_length=len(''.join(collected_answer_parts).strip()),
        )

        yield {
            'event': 'final',
            'payload': {
                'thread_id': thread_id,
                'query': question,
                'answer': ''.join(collected_answer_parts).strip(),
                'evidence': evidence,
                'clue_state': clue_state,
                'candidate_review': candidate_review,
                'process_trace': process_trace,
            },
        }

    def _default_clue_state(self):
        return {
            'confirmed_clues': [],
            'uncertain_clues': [],
            'excluded_titles': [],
            'negative_feedback': [],
            'last_candidates': [],
            'turn_count': 0,
        }

    def _begin_clue_state_turn(self, thread_id):
        state = self.thread_states.setdefault(thread_id, self._default_clue_state())
        state['turn_count'] += 1
        return state

    def _elapsed_ms(self, start_time):
        return round((time.perf_counter() - start_time) * 1000, 2)

    def _log_turn_summary(
        self,
        event,
        thread_id,
        start_time,
        search_events,
        evidence,
        process_trace,
        candidate_review,
        **extra,
    ):
        _log_agent_event(
            event,
            thread_id=thread_id,
            duration_ms=self._elapsed_ms(start_time),
            search_event_count=len(search_events or []),
            evidence_count=len(evidence or []),
            clue_step_count=len(process_trace.get('clue_steps', [])),
            retrieval_step_count=len(process_trace.get('retrieval_steps', [])),
            candidate_step_count=len(process_trace.get('candidate_steps', [])),
            review_source=(candidate_review or {}).get('review_source'),
            **extra,
        )

    def _log_stream_event(self, thread_id, translated, stream_start):
        event_type = translated.get('event')
        payload = translated.get('payload') or {}
        log_payload = {
            'thread_id': thread_id,
            'elapsed_ms': self._elapsed_ms(stream_start),
        }
        if event_type in ('subagent_start', 'subagent_result'):
            log_payload['stage'] = payload.get('stage')
        if event_type == 'answer_token':
            log_payload['token_length'] = len(payload.get('text') or '')
        _log_agent_event(f'agent.stream.{event_type}', **log_payload)

    def _build_turn_prompt(self, question, clue_state):
        clue_state_text = self._format_clue_state(clue_state)
        return f"""用户问题：
{question}

上一轮 LLM 线索状态：
{clue_state_text}

请按需处理：
- 非找电影请求：直接简短回答，不调用子 Agent。
- 新线索/修正/否认/复杂上下文：可调用 clue_extractor。
- 需要新候选：调用 movie_retriever。
- 有新候选且需要判断：调用 candidate_verifier。
- 线索不足或候选不稳：只追问一个关键问题。
"""

    def _sync_clue_state(self, clue_state, process_trace):
        for clue_step in process_trace.get('clue_steps') or []:
            self._apply_clue_state_update(clue_state, clue_step)
        return clue_state

    def _apply_clue_state_update(self, clue_state, update):
        field_mapping = {
            'confirmed_clues': 'confirmed_clues',
            'uncertain_clues': 'uncertain_clues',
            'exclusions': 'excluded_titles',
            'excluded_titles': 'excluded_titles',
            'negative_feedback': 'negative_feedback',
        }
        for source_key, target_key in field_mapping.items():
            if source_key in update:
                clue_state[target_key] = self._normalize_llm_list(update.get(source_key))
        return clue_state

    def _normalize_llm_list(self, values):
        if not isinstance(values, list):
            return []

        normalized = []
        for value in values:
            if isinstance(value, str):
                cleaned = value.strip()
            else:
                cleaned = str(value).strip()
            self._append_unique(normalized, cleaned)
        return normalized

    def _append_unique(self, items, value):
        if value and value not in items:
            items.append(value)

    def _set_last_candidates(self, clue_state, evidence):
        clue_state['last_candidates'] = []
        for item in evidence:
            self._append_unique(clue_state['last_candidates'], item.get('movie_title'))

    def _extract_evidence_from_search_events(self, search_events, max_results, clue_state):
        excluded = set(clue_state.get('excluded_titles', []))
        evidence = []
        seen = set()
        for event in reversed(search_events or []):
            for item in event.get('results', []):
                item_id = item.get('id')
                if item_id in seen or item.get('movie_title') in excluded:
                    continue
                seen.add(item_id)
                evidence.append(item)
                if len(evidence) >= max_results:
                    return evidence
        return evidence

    def _extract_process_trace(self, messages):
        return {
            'clue_steps': self._extract_subagent_outputs(messages, 'clue_extractor'),
            'retrieval_steps': self._extract_subagent_outputs(messages, 'movie_retriever'),
            'candidate_steps': self._extract_subagent_outputs(messages, 'candidate_verifier'),
        }

    def _extract_subagent_outputs(self, messages, subagent_type):
        outputs = []
        task_calls = {}
        for message in messages or []:
            tool_calls = getattr(message, 'tool_calls', None) or []
            for tool_call in tool_calls:
                if tool_call.get('name') != 'task':
                    continue
                tool_call_id = tool_call.get('id')
                if not tool_call_id:
                    continue
                args = tool_call.get('args') or {}
                task_calls[tool_call_id] = args.get('subagent_type')

            tool_call_id = getattr(message, 'tool_call_id', None)
            if not tool_call_id or task_calls.get(tool_call_id) != subagent_type:
                continue

            content = self._content_to_text(getattr(message, 'content', ''))
            if not content:
                continue

            try:
                parsed = self._parse_json_object(content)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

            if isinstance(parsed, dict):
                outputs.append(parsed)
        return outputs

    def _resolve_candidate_review(self, process_trace, evidence, clue_state):
        candidate_steps = process_trace.get('candidate_steps', [])
        if candidate_steps:
            review = dict(candidate_steps[-1])
            review['review_source'] = 'candidate_verifier'
            return review

        if not evidence:
            return {
                'candidates': [],
                'should_ask_followup': False,
                'followup_question': '',
                'review_summary': '本轮没有候选片段需要验证。',
                'review_source': 'not_applicable',
            }

        return {
            'candidates': [],
            'should_ask_followup': True,
            'followup_question': '候选验证没有返回结构化结果，请补充一个更具体的情节、人物身份或场景线索。',
            'review_summary': 'candidate_verifier 未返回结构化验证结果。',
            'review_source': 'verifier_missing',
        }

    def _append_process_step(self, process_trace, payload):
        stage = payload.get('stage')
        data = payload.get('data')
        if not stage or not isinstance(data, dict):
            return

        mapping = {
            'clue_extractor': 'clue_steps',
            'movie_retriever': 'retrieval_steps',
            'candidate_verifier': 'candidate_steps',
        }
        target = mapping.get(stage)
        if target:
            process_trace[target].append(data)

    def _content_to_text(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get('text')
                    if text:
                        parts.append(text)
            return '\n'.join(parts)
        return str(content or '')

    def _parse_json_object(self, text):
        text = text.strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def _format_clue_state(self, clue_state):
        return '\n'.join(
            [
                f"- 确定线索：{', '.join(clue_state.get('confirmed_clues', [])[-12:]) or '暂无'}",
                f"- 不确定线索：{', '.join(clue_state.get('uncertain_clues', [])[-8:]) or '暂无'}",
                f"- 排除候选：{', '.join(clue_state.get('excluded_titles', [])) or '暂无'}",
                f"- 用户否认：{'; '.join(clue_state.get('negative_feedback', [])[-3:]) or '暂无'}",
                f"- 上轮候选：{', '.join(clue_state.get('last_candidates', [])) or '暂无'}",
            ]
        )

    def _translate_stream_event(self, event, collected_answer_parts):
        if not isinstance(event, tuple) or len(event) != 3:
            return None

        namespace, mode, payload = event
        namespace_key = tuple(namespace)

        if mode == 'updates':
            return None

        if mode == 'messages':
            chunk, metadata = payload
            if metadata.get('langgraph_node') != 'model':
                return None
            if namespace_key:
                return None
            content = getattr(chunk, 'content', '')
            text = self._content_to_text(content)
            if not text:
                return None
            collected_answer_parts.append(text)
            return {'event': 'answer_token', 'payload': {'text': text}}

        if mode != 'tasks' or not isinstance(payload, dict):
            return None

        task_calls = _stream_task_calls.get()
        if task_calls is None:
            return None

        name = payload.get('name')
        if name == 'tools':
            tool_calls = payload.get('input') or []
            emitted_start = None
            for tool_call in tool_calls:
                if tool_call.get('name') != 'task':
                    continue
                tool_call_id = tool_call.get('id')
                args = tool_call.get('args') or {}
                subagent_type = args.get('subagent_type')
                if not tool_call_id or not subagent_type:
                    continue
                task_calls[tool_call_id] = subagent_type
                if emitted_start is None:
                    emitted_start = {
                        'event': 'subagent_start',
                        'payload': {
                            'stage': subagent_type,
                            'title': self._subagent_title(subagent_type),
                            'description': args.get('description', ''),
                        },
                    }

            result = payload.get('result') or {}
            messages = result.get('messages') or []
            for message in messages:
                tool_call_id = getattr(message, 'tool_call_id', None)
                subagent_type = task_calls.get(tool_call_id)
                if not subagent_type:
                    continue
                content = self._content_to_text(getattr(message, 'content', ''))
                parsed = self._parse_json_payload_safe(content)
                if parsed is None:
                    continue
                return {
                    'event': 'subagent_result',
                    'payload': self._build_stream_process_payload(subagent_type, parsed),
                }
            return emitted_start

        return None

    def _build_stream_process_payload(self, subagent_type, parsed):
        return {
            'stage': subagent_type,
            'title': self._subagent_title(subagent_type),
            'data': parsed,
        }

    def _subagent_title(self, subagent_type):
        titles = {
            'clue_extractor': '线索提取',
            'movie_retriever': '执行检索',
            'candidate_verifier': '候选验证',
        }
        return titles.get(subagent_type, subagent_type)

    def _parse_json_payload_safe(self, text):
        try:
            return self._parse_json_object(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None


movie_search_agent = MovieSearchAgent()
