from elasticsearch import Elasticsearch
from movies.models import Movie, Actor, Director, Segment
import json
import os

class importDataES:
    def __init__(self):
        self.es = Elasticsearch([os.environ.get('ELASTICSEARCH_URL')])

    def import_data(self, content, target_index):
        doc_id = f"{content['movie_id']}_{content['segment_index']}"
        if not self.es.exists(index=target_index, id=doc_id):
            self.es.index(index=target_index, id=doc_id, body=content)
            print(f"Document with ID {doc_id} imported into index {target_index}.")
        else:
            print(f"Document with ID {doc_id} already exists in index {target_index}. Skipping import.")

class importDataDB:

    def import_data(self, content, import_type):

        if import_type == "movie":
            actors = content.get('actors', [])
            director = content.get('director', None)

            director_obj = Director.objects.get(director_name=director)

            actor_objs = []
            for actor in actors:
                actor_obj = Actor.objects.get(actor_name=actor)
                actor_objs.append(actor_obj)


            movie_id = content.get('movie_id', None)
            movie_title = content.get('movie_title', None)
            year = content.get('year', None)
            genre = content.get('genre', None)

            tags = content.get('tags', None)
            description = content.get('description', None)
            rating = content.get('rating', None)
            
            movie = Movie.objects.create(
                movie_id=movie_id,
                movie_title=movie_title,
                year=year,
                genre=genre,
                tags=tags,
                description=description,
                rating=rating
            )

            movie.actors.set(actor_objs)
            movie.directors.add(director_obj)

            print(f"Movie with ID {movie_id} imported into database.")

        elif import_type == "actor":
            
            actor_name = content.get('actor_name', None)

            actor = Actor.objects.get_or_create(
                actor_name=actor_name,
            )

            print(f"Actor {actor_name} imported into database.")

        elif import_type == "director":

            director_name = content.get('director_name', None)

            director = Director.objects.get_or_create(
                director_name=director_name,
            )

            print(f"Director {director_name} imported into database.")

        elif import_type == "segment":

            movie_id = content.get('movie_id', None)
            segment_order = content.get('segment_order', None)
            script_content = content.get('script_content', None)
            summary_content = content.get('summary_content', None)

            movie = Movie.objects.get(movie_id=movie_id)

            segment = Segment.objects.create(
                movie=movie,
                segment_order=segment_order,
                script_content=script_content,
                summary_content=summary_content
            )

            print(f"Segment with ID {segment.segment_id} imported into database.")





