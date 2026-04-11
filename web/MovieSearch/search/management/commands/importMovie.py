import json
from django.core.management.base import BaseCommand

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from concurrent.futures import ThreadPoolExecutor, as_completed

from search.utils.importData import importData
import os

class Command(BaseCommand):
    help = 'Import movie data from json file to database and elasticsearch'

    def add_arguments(self, parser):
        parser.add_argument('--path', required=True, help='Path to the json file')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--es', action='store_true', help='Import to elasticsearch')
        group.add_argument('--db', action='store_true', help='Import to database')

    def handle(self, *args, **options):
        file_path = options['path']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} does not exist.'))
            return

        if options['es']:
            self.import_to_es(file_path)
        elif options['db']:
            self.import_to_db(file_path)

    def import_to_es(self, file_path):
        DataImporter = importData()

        for file in os.listdir(file_path):
            if file.endswith(".json"):
                with open(os.path.join(file_path, file), 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    DataImporter.import_data(content=content, target_index='movies')

    


            
