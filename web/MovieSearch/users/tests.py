from django.test import SimpleTestCase
from django.urls import reverse


class UserUrlTests(SimpleTestCase):
    def test_account_urls_are_namespaced(self):
        self.assertEqual(reverse('users:login'), '/accounts/login/')
        self.assertEqual(reverse('users:register'), '/accounts/register/')
        self.assertEqual(reverse('users:logout'), '/accounts/logout/')
