from search.utils.embeddingData import embeddingData
from search.utils.sliceData import sliceData
from search.utils.getSummary import getSummary
from search.utils.importData import importDataES, importDataDB
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
    def __init__(self, dataPipeline, basic_info_path):
        self.dataPipeline = dataPipeline
        self.db_importer = importDataDB()
        self.es_importer = importDataES()
        
        with open(basic_info_path, 'r', encoding='utf-8') as f:
            self.basic_info = json.load(f)

        """    {
        "movie_title": "阿甘正传",
        "genre": "剧情, 爱情, 励志",
        "year": 1994,
        "director": "罗伯特·泽米吉斯",
        "actors": ["汤姆·汉克斯", "罗宾·怀特", "加里·西尼斯"],
        "tags": ["励志", "人生", "经典", "奥斯卡"]
        "descrption": ""
        "rating": "8.6",
        
        },"""

    def struct_Es(self, 
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

    def struct_DBmovie(self, 
                    movie_id,
                    movie_title,
                    genre,
                    year,
                    director,
                    actors,
                    tags,
                    description, 
                    rating):
        
        base = sample_document = {
            "movie_id": movie_id,
            "movie_title": movie_title,
            "genre": genre,
            "year": year,
            "director": director,
            "actors": actors,
            "tags": tags,
            "description": description,
            "rating": rating,
        }
        return base

    def struct_DBactor(self, actor_name,):
        
        base = sample_document = {
            "actor_name": actor_name,
        }
        return base

    def struct_DBdirector(self, director_name,):
        
        base = sample_document = {
            "director_name": director_name,
        }
        return base

    def struct_DBsegment(self, segment_order, movie_id, script, summary):
        base = sample_document = {
            "segment_order": segment_order,
            "movie_id": movie_id,
            "script_content": script,
            "summary_content": summary,
        }
        return base

    def process_segment(self, data_list, movie_title):

        for segment_index, data in enumerate(data_list):
            
            segment_index += 1
            save_path = f"data_cache/es_cache/{movie_title}_segment_{segment_index}.json"

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

            es_data   = self.struct_Es(movie_id, 
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
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(es_data, f, ensure_ascii=False, indent=4)
                print(f"保存ES数据到 {save_path} 成功")

            try:
                self.es_importer.import_data(content=es_data, target_index="movies")
            except Exception as e:
                print(f"导入ES失败，错误信息：{e}")

            db_data = self.struct_DBsegment(segment_order=segment_index, 
                                            movie_id=movie_id, 
                                            script=data,    
                                            summary=summary)

            try:
                self.db_importer.import_data(db_data, import_type="segment")
            except Exception as e:
                print(f"segment导入DB失败，错误信息：{e}")
            
    def process_basic(self, data_list, movie_title):

        save_path = f"data_cache/db_cache/{movie_title}.json"

        if os.path.exists(save_path):
            return None

        db_data = self.struct_DBmovie(movie_id=self.basic_info[movie_title]["movie_id"], 
                                        movie_title=movie_title, 
                                        genre=self.basic_info[movie_title]["genre"], 
                                        year=self.basic_info[movie_title]["year"], 
                                        director=self.basic_info[movie_title]["director"], 
                                        actors=self.basic_info[movie_title]["actors"], 
                                        tags=self.basic_info[movie_title]["tags"], 
                                        description=self.basic_info[movie_title]["description"], 
                                        rating=self.basic_info[movie_title]["rating"])
        
        for actor in self.basic_info[movie_title]["actors"]:
            db_actor = self.struct_DBactor(actor_name=actor)
            try:
                self.db_importer.import_data(db_actor, import_type="actor")
            except Exception as e:
                print(f"actor导入DB失败，错误信息：{e}")

        db_director = self.struct_DBdirector(director_name=self.basic_info[movie_title]["director"])

        try:
            self.db_importer.import_data(db_director, import_type="director")
        except Exception as e:
            print(f"director导入DB失败，错误信息：{e}")

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, ensure_ascii=False, indent=4)
            print(f"保存DB数据到 {save_path} 成功")

        try:
            self.db_importer.import_data(db_data, import_type="movie")
        except Exception as e:
            print(f"basic_info导入DB失败，错误信息：{e}")

    def process_data(self):
        print("开始处理数据")

        while True:

            file_path = self.dataPipeline.get_file_path()
            data_list = sliceData().slice_script(file_path)

            movie_title = os.path.basename(file_path).split('.')[0]

            print(f"正在处理 {movie_title} 文件")
            
            self.process_basic(data_list, movie_title)
            self.process_segment(data_list, movie_title)
            time.sleep(1)

            stop = self.dataPipeline.update_index()
            if stop is None:
                break

if __name__ == '__main__':
    data_path = "movies"
    dataPipeline = DataPipeline(data_path)
    DataProcessor = processData(dataPipeline)
    DataProcessor.process_data()

                