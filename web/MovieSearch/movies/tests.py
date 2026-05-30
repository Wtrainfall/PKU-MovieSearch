from django.test import SimpleTestCase
from django.urls import reverse


class HomeUrlTests(SimpleTestCase):
    def test_home_url_is_namespaced(self):
        self.assertEqual(reverse('movies:home'), '/')

    def test_homepage_renders_reversed_search_urls(self):
        response = self.client.get(reverse('movies:home'))
        self.assertContains(response, reverse('search:agent'))
        self.assertContains(response, reverse('search:stats'))
