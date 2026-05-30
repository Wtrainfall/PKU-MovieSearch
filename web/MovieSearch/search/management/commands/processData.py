import json
from django.core.management.base import BaseCommand
from search.utils.processData import processData, DataPipeline
import os

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str)

    def handle(self, *args, **options):
        path = options['path']
        data_pipeline = DataPipeline(path)
        data_processor = processData(dataPipeline=data_pipeline, basic_info_path=os.path.join(path, 'basic/basic_info.json'))
        data_processor.process_data()
