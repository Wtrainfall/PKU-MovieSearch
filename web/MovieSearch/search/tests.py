from django.test import SimpleTestCase
from django.urls import reverse


class SearchUrlTests(SimpleTestCase):
    def test_search_urls_use_search_namespace(self):
        self.assertEqual(reverse('search:api'), '/search/api/')
        self.assertEqual(reverse('search:agent'), '/search/agent/')
        self.assertEqual(reverse('search:stats'), '/search/stats/')
