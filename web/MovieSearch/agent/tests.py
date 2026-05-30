import os
from unittest.mock import patch

from django.test import SimpleTestCase

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
