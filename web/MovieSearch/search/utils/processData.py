from embeddingData import embeddingData
from sliceData import sliceData
from getSummary import getSummary
from importData import importData
import os 
import time
import json

class DataPipeline:
    def __init__(self, data_path):
        self.data_path = data_path
        self.current_index = 0
        self.total_count = self.get_file_count()
    
    def get_file_count(self):

        file_count = 0
        for file in os.listdir(self.data_path):
            if file.endswith('.txt'):
                file_count += 1
        
        return file_count
    
    def update_index(self):
        if self.current_index >= self.total_count-1:
            print("处理完毕")
            return None
        self.current_index += 1
        print(f"处理文件 {self.current_index}/{self.total_count}")
        return self.current_index
    
    def get_file_path(self):
        file_list = [file for file in os.listdir(self.data_path) if file.endswith('.txt')]
        if self.current_index < len(file_list):
            file_path = os.path.join(self.data_path, file_list[self.current_index])
            return file_path
        else:
            return None
    

class processData:
    def __init__(self, dataPipeline):
        self.dataPipeline = dataPipeline

        path = r'movies\basic\basic_info.json'
        with open(path, 'r', encoding='utf-8') as f:
            self.basic_info = json.load(f)

        """    {
        "movie_title": "阿甘正传",
        "genre": "剧情, 爱情, 励志",
        "year": "1994",
        "director": "罗伯特·泽米吉斯",
        "actors": ["汤姆·汉克斯", "罗宾·怀特", "加里·西尼斯"],
        "tags": ["励志", "人生", "经典", "奥斯卡"]
        
        },"""

    def struct_data(self, 
                    movie_id,
                    movie_title,
                    genre,
                    year,
                    director,
                    actors,
                    tags,
                    segment_index, 
                    script, 
                    summary, 
                    embedding_summary, 
                    embedding_script):
        
        base = sample_document = {
            "movie_id": movie_id,
            "movie_title": movie_title,
            "segment_index": segment_index,
            "genre": genre,
            "year": year,
            "director": director,
            "actors": actors,
            "tags": tags,
            "script": script,
            "summary": summary,
            "embedding_summary": embedding_summary,   
            "embedding_script": embedding_script,
        }
        return base

    def process_data(self):
        print("开始处理数据")
        while True:
            file_path = self.dataPipeline.get_file_path()
            data_list = sliceData().slice_script(file_path)

            movie_title = os.path.basename(file_path).split('.')[0]

            print(f"正在处理 {movie_title} 文件")

            for segment_index, data in enumerate(data_list):
                
                segment_index += 1
                save_path = f"processed_data/{movie_title}_segment_{segment_index}.json"
                if os.path.exists(save_path):
                    continue

                try:
                    summary = getSummary().get_summary(data)
                except Exception as e:
                    print(f"获取摘要失败，错误信息：{e}")
                    summary = "暂无"

                content_embedding = embeddingData().get_embedding(data)
                summary_embedding = embeddingData().get_embedding(summary)

                movie_id = self.basic_info[movie_title]["movie_id"]
                segment_index = segment_index
                genre = self.basic_info[movie_title]["genre"]
                year = self.basic_info[movie_title]["year"]
                director = self.basic_info[movie_title]["director"]
                actors = self.basic_info[movie_title]["actors"]
                tags = self.basic_info[movie_title]["tags"]

                base   = self.struct_data(movie_id, 
                                           movie_title, 
                                           genre, 
                                           year, 
                                           director, 
                                           actors, 
                                           tags, 
                                           segment_index, 
                                           data, 
                                           summary, 
                                           summary_embedding, 
                                           content_embedding)
                
                #保存base到文件
                if not os.path.exists(os.path.dirname(save_path)):
                    os.makedirs(os.path.dirname(save_path))

                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(base, f, ensure_ascii=False, indent=4)
                
                time.sleep(1)

            stop = self.dataPipeline.update_index()
            if stop is None:
                break

if __name__ == '__main__':
    data_path = "movies"
    dataPipeline = DataPipeline(data_path)
    DataProcessor = processData(dataPipeline)
    DataProcessor.process_data()

    processed_data_path = r'processed_data'

    for file in os.listdir(processed_data_path):
        if file.endswith('.json'):
            with open(os.path.join(processed_data_path, file), 'r', encoding='utf-8') as f:
                content = json.load(f)
                DataImporter = importData(target_index='movies', content=content)
                DataImporter.import_data()
    
                