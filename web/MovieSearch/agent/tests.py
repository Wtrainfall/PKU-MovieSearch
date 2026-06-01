import os
import json
from unittest.mock import patch

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, ToolMessage

from agent.agent import MovieSearchAgent
from agent.views import _stream_agent_events
from config.qwen import (
    DEFAULT_QWEN_BASE_URL,
    DEFAULT_QWEN_CHAT_MODEL,
    DEFAULT_QWEN_EMBEDDING_MODEL,
    build_qwen_chat_model,
    build_qwen_client,
    get_qwen_chat_model,
    get_qwen_embedding_model,
    require_env,
)


class QwenConfigTests(SimpleTestCase):
    def test_require_env_raises_for_missing_qwen_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(RuntimeError, '缺少环境变量: QWEN_API_KEY'):
                require_env('QWEN_API_KEY')

    @patch('config.qwen.OpenAI')
    def test_build_qwen_client_uses_shared_qwen_settings(self, openai_cls):
        with patch.dict(
            os.environ,
            {
                'QWEN_API_KEY': 'test-qwen-key',
                'QWEN_BASE_URL': 'https://example.invalid/compatible/v1',
            },
            clear=True,
        ):
            build_qwen_client()

        openai_cls.assert_called_once_with(
            api_key='test-qwen-key',
            base_url='https://example.invalid/compatible/v1',
        )

    @patch('config.qwen.ChatOpenAI')
    def test_build_qwen_chat_model_uses_specific_model_override(self, chat_cls):
        with patch.dict(
            os.environ,
            {
                'QWEN_API_KEY': 'test-qwen-key',
                'QWEN_AGENT_MODEL': 'qwen-max',
            },
            clear=True,
        ):
            build_qwen_chat_model(model_env='QWEN_AGENT_MODEL', temperature=0)

        chat_cls.assert_called_once_with(
            model='qwen-max',
            api_key='test-qwen-key',
            base_url=DEFAULT_QWEN_BASE_URL,
            temperature=0,
        )

    def test_qwen_model_defaults_are_consistent(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_qwen_chat_model('QWEN_SUMMARY_MODEL'), DEFAULT_QWEN_CHAT_MODEL)
            self.assertEqual(get_qwen_embedding_model(), DEFAULT_QWEN_EMBEDDING_MODEL)

    def test_qwen_chat_model_falls_back_to_shared_chat_model(self):
        with patch.dict(os.environ, {'QWEN_CHAT_MODEL': 'qwen-turbo'}, clear=True):
            self.assertEqual(get_qwen_chat_model('QWEN_SUMMARY_MODEL'), 'qwen-turbo')


class AgentProcessTraceTests(SimpleTestCase):
    def setUp(self):
        self.agent = MovieSearchAgent()

    def test_extract_process_trace_reads_structured_subagent_outputs(self):
        clue_payload = {
            'confirmed_clues': ['失明军官', '年轻学生'],
            'uncertain_clues': ['可能是外国片'],
            'exclusions': [],
            'enough_for_search': True,
            'followup_question': '',
            'rationale': '线索具备辨识度。',
        }
        retrieval_payload = {
            'search_queries': ['失明军官 学生', 'blind colonel'],
            'candidates': [
                {
                    'movie_title': '闻香识女人',
                    'segment_index': 7,
                    'evidence_id': '12_7',
                    'summary': '失明军官与学生互动。',
                    'relevance': '人物关系高度匹配。',
                }
            ],
            'retrieval_summary': '候选集中在同一电影。',
            'gap_analysis': '',
        }
        candidate_payload = {
            'candidates': [
                {
                    'movie_title': '闻香识女人',
                    'segment_index': 7,
                    'confidence': 'high',
                    'matched_clues': ['失明军官', '年轻学生'],
                    'missing_clues': [],
                    'conflicts': [],
                }
            ],
            'should_ask_followup': False,
            'followup_question': '',
            'review_summary': '候选与核心线索匹配。',
        }
        messages = [
            AIMessage(
                content='',
                tool_calls=[
                    {
                        'name': 'task',
                        'args': {'subagent_type': 'clue_extractor'},
                        'id': 'call-clue',
                        'type': 'tool_call',
                    }
                ],
            ),
            ToolMessage(json.dumps(clue_payload, ensure_ascii=False), tool_call_id='call-clue'),
            AIMessage(
                content='',
                tool_calls=[
                    {
                        'name': 'task',
                        'args': {'subagent_type': 'movie_retriever'},
                        'id': 'call-retriever',
                        'type': 'tool_call',
                    }
                ],
            ),
            ToolMessage(json.dumps(retrieval_payload, ensure_ascii=False), tool_call_id='call-retriever'),
            AIMessage(
                content='',
                tool_calls=[
                    {
                        'name': 'task',
                        'args': {'subagent_type': 'candidate_verifier'},
                        'id': 'call-candidate',
                        'type': 'tool_call',
                    }
                ],
            ),
            ToolMessage(json.dumps(candidate_payload, ensure_ascii=False), tool_call_id='call-candidate'),
        ]

        trace = self.agent._extract_process_trace(messages)

        self.assertEqual(trace['clue_steps'][0]['confirmed_clues'], ['失明军官', '年轻学生'])
        self.assertEqual(trace['retrieval_steps'][0]['search_queries'], ['失明军官 学生', 'blind colonel'])
        self.assertEqual(trace['candidate_steps'][0]['candidates'][0]['movie_title'], '闻香识女人')

    def test_sync_clue_state_applies_clue_extractor_output(self):
        clue_state = self.agent._default_clue_state()
        clue_state['confirmed_clues'] = ['本地旧线索']
        clue_state['last_candidates'] = ['旧候选']
        process_trace = {
            'clue_steps': [
                {
                    'confirmed_clues': ['失明军官', '年轻学生', '失明军官', ''],
                    'uncertain_clues': ['可能是外国片'],
                    'exclusions': ['旧候选'],
                    'negative_feedback': ['不是刚才那个'],
                }
            ],
            'retrieval_steps': [],
            'candidate_steps': [],
        }

        self.agent._sync_clue_state(clue_state, process_trace)

        self.assertEqual(clue_state['confirmed_clues'], ['失明军官', '年轻学生'])
        self.assertEqual(clue_state['uncertain_clues'], ['可能是外国片'])
        self.assertEqual(clue_state['excluded_titles'], ['旧候选'])
        self.assertEqual(clue_state['negative_feedback'], ['不是刚才那个'])
        self.assertEqual(clue_state['last_candidates'], ['旧候选'])

    def test_sync_clue_state_uses_latest_clue_extractor_output(self):
        clue_state = self.agent._default_clue_state()
        process_trace = {
            'clue_steps': [
                {
                    'confirmed_clues': ['旧线索'],
                    'uncertain_clues': [],
                    'exclusions': [],
                    'negative_feedback': [],
                },
                {
                    'confirmed_clues': ['子Agent线索'],
                    'uncertain_clues': ['子Agent不确定'],
                    'exclusions': ['子Agent排除'],
                    'negative_feedback': ['子Agent否认'],
                },
            ],
            'retrieval_steps': [],
            'candidate_steps': [],
        }

        self.agent._sync_clue_state(clue_state, process_trace)

        self.assertEqual(clue_state['confirmed_clues'], ['子Agent线索'])
        self.assertEqual(clue_state['uncertain_clues'], ['子Agent不确定'])
        self.assertEqual(clue_state['excluded_titles'], ['子Agent排除'])
        self.assertEqual(clue_state['negative_feedback'], ['子Agent否认'])

    def test_turn_prompt_allows_direct_reply_without_subagents(self):
        prompt = self.agent._build_turn_prompt('你好', self.agent._default_clue_state())

        self.assertIn('非找电影请求：直接简短回答，不调用子 Agent', prompt)
        self.assertNotIn('每一轮必须先调用 clue_extractor', prompt)

    def test_turn_prompt_routes_subagents_only_when_needed(self):
        prompt = self.agent._build_turn_prompt('一个失明军官和年轻学生的电影', self.agent._default_clue_state())

        self.assertIn('新线索/修正/否认/复杂上下文：可调用 clue_extractor', prompt)
        self.assertIn('需要新候选：调用 movie_retriever', prompt)
        self.assertIn('有新候选且需要判断：调用 candidate_verifier', prompt)
        self.assertIn('线索不足或候选不稳：只追问一个关键问题', prompt)
        self.assertNotIn('update_clue_state', prompt)

    def test_resolve_candidate_review_prefers_candidate_verifier_output(self):
        process_trace = {
            'clue_steps': [],
            'retrieval_steps': [],
            'candidate_steps': [
                {
                    'candidates': [{'movie_title': '闻香识女人', 'segment_index': 7, 'confidence': 'high', 'matched_clues': [], 'missing_clues': [], 'conflicts': []}],
                    'should_ask_followup': False,
                    'followup_question': '',
                    'review_summary': '匹配。',
                }
            ],
        }

        review = self.agent._resolve_candidate_review(process_trace, [], self.agent._default_clue_state())

        self.assertEqual(review['review_source'], 'candidate_verifier')
        self.assertEqual(review['candidates'][0]['movie_title'], '闻香识女人')

    def test_resolve_candidate_review_is_not_applicable_without_evidence(self):
        review = self.agent._resolve_candidate_review(
            {'clue_steps': [], 'retrieval_steps': [], 'candidate_steps': []},
            [],
            self.agent._default_clue_state(),
        )

        self.assertEqual(review['review_source'], 'not_applicable')
        self.assertFalse(review['should_ask_followup'])
        self.assertEqual(review['candidates'], [])

    def test_resolve_candidate_review_reports_missing_verifier_output(self):
        clue_state = self.agent._default_clue_state()

        review = self.agent._resolve_candidate_review(
            {'clue_steps': [], 'retrieval_steps': [], 'candidate_steps': []},
            [{'movie_title': '阿甘正传', 'segment_index': 1}],
            clue_state,
        )

        self.assertEqual(review['review_source'], 'verifier_missing')
        self.assertEqual(review['candidates'], [])
        self.assertTrue(review['should_ask_followup'])

    def test_translate_stream_event_emits_subagent_start(self):
        self.agent_module = __import__('agent.agent', fromlist=['_stream_task_calls'])
        token = self.agent_module._stream_task_calls.set({})
        try:
            event = (
                (),
                'tasks',
                {
                    'name': 'tools',
                    'input': [
                        {
                            'name': 'task',
                            'args': {'subagent_type': 'movie_retriever', 'description': '执行检索'},
                            'id': 'call-retriever',
                            'type': 'tool_call',
                        }
                    ],
                },
            )
            translated = self.agent._translate_stream_event(event, [])
        finally:
            self.agent_module._stream_task_calls.reset(token)

        self.assertEqual(translated['event'], 'subagent_start')
        self.assertEqual(translated['payload']['stage'], 'movie_retriever')

    def test_translate_stream_event_emits_subagent_result(self):
        self.agent_module = __import__('agent.agent', fromlist=['_stream_task_calls'])
        token = self.agent_module._stream_task_calls.set({'call-candidate': 'candidate_verifier'})
        try:
            event = (
                (),
                'tasks',
                {
                    'name': 'tools',
                    'result': {
                        'messages': [
                            ToolMessage(
                                json.dumps(
                                    {
                                        'candidates': [],
                                        'should_ask_followup': True,
                                        'followup_question': '再补充线索',
                                        'review_summary': '无匹配候选',
                                    },
                                    ensure_ascii=False,
                                ),
                                tool_call_id='call-candidate',
                            )
                        ]
                    },
                },
            )
            translated = self.agent._translate_stream_event(event, [])
        finally:
            self.agent_module._stream_task_calls.reset(token)

        self.assertEqual(translated['event'], 'subagent_result')
        self.assertEqual(translated['payload']['stage'], 'candidate_verifier')

    @patch('agent.views.movie_search_agent')
    def test_stream_agent_events_forwards_process_events(self, movie_search_agent):
        movie_search_agent.stream.return_value = iter(
            [
                {
                    'event': 'subagent_start',
                    'payload': {
                        'stage': 'movie_retriever',
                        'title': '执行检索',
                        'description': '检索候选',
                    },
                },
                {
                    'event': 'subagent_result',
                    'payload': {
                        'stage': 'movie_retriever',
                        'title': '执行检索',
                        'data': {'search_queries': ['失明军官 年轻学生']},
                    },
                },
                {
                    'event': 'final',
                    'payload': {
                        'answer': '可能是闻香识女人。',
                        'process_trace': {
                            'clue_steps': [],
                            'retrieval_steps': [{'search_queries': ['失明军官 年轻学生']}],
                            'candidate_steps': [],
                        },
                    },
                },
            ]
        )

        body = ''.join(_stream_agent_events('问题', 'thread-test'))

        self.assertIn('event: subagent_start', body)
        self.assertIn('event: process', body)
        self.assertIn('event: final', body)
        self.assertIn('失明军官 年轻学生', body)
