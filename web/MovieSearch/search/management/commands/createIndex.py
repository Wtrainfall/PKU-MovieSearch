from search.utils.createIndex import createIndex
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        IndexCreater = createIndex()
        IndexCreater.create_index()
        self.stdout.write(self.style.SUCCESS('Index created successfully'))