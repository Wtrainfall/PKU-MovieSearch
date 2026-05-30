import json
from django.core.management.base import BaseCommand

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from concurrent.futures import ThreadPoolExecutor, as_completed

from search.utils.importData import importDataES, importDataDB
import os

class Command(BaseCommand):
    help = 'Import movie data from json file to database and elasticsearch'

    def add_arguments(self, parser):
        parser.add_argument('--path', required=True, help='Path to the json file')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--es', action='store_true', help='Import to elasticsearch')
        group.add_argument('--db', action='store_true', help='Import to database')
        
        parser.add_argument('--type', '-t', choices=['movie', 'actor', 'director'], help='Type of import')

    def handle(self, *args, **options):
        file_path = options['path']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} does not exist.'))
            return

        if options['es']:
            self.import_to_es(file_path)
        elif options['db']:
            import_type = options['type']
            if not import_type:
                self.stdout.write(self.style.ERROR('Please specify the type of import.'))
                return
            self.import_to_db(file_path, import_type)

    def import_to_es(self, file_path):
        DataImporter = importDataES()

        for file in os.listdir(file_path):
            if file.endswith(".json"):
                with open(os.path.join(file_path, file), 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    try:
                        DataImporter.import_data(content=content, target_index='movies')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error importing data to elasticsearch: {e}'))

    def import_to_db(self, file_path, import_type):
        DataImporter = importDataDB()

        for file in os.listdir(file_path):
            if file.endswith(".json"):
                with open(os.path.join(file_path, file), 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    try:
                        DataImporter.import_data(content=content, import_type=import_type)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error importing data to database: {e}'))
    
        




            
