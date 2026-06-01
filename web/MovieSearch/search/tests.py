from django.test import SimpleTestCase
from django.urls import reverse

from search.utils.queryData import simplify_results


class SearchUrlTests(SimpleTestCase):
    def test_search_urls_use_search_namespace(self):
        self.assertEqual(reverse('search:api'), '/search/api/')
        self.assertEqual(reverse('search:agent'), '/search/agent/')
        self.assertEqual(reverse('search:stats'), '/search/stats/')


class SearchResultFormatTests(SimpleTestCase):
    def test_simplified_results_include_movie_id(self):
        results = simplify_results(
            [
                {
                    'id': '2_1',
                    'score': 0.1,
                    'sources': ['keyword'],
                    'ranks': {'keyword': 1},
                    'source': {
                        'movie_id': '2',
                        'movie_title': '楚门的世界',
                        'segment_index': 1,
                        'summary': '摘要',
                        'script': '剧本',
                    },
                }
            ]
        )

        self.assertEqual(results[0]['movie_id'], '2')
