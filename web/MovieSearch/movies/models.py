from django.db import models

# Create your models here.
class Movie(models.Model):

    #base fields
    movie_id = models.IntegerField(primary_key=True, unique=True)
    movie_title = models.CharField(max_length=255)
    year = models.IntegerField(null=True, blank=True)
    genre = models.CharField(max_length=255, null=True, blank=True)

    actors = models.ManyToManyField('Actor', related_name='movies', blank=True)
    directors = models.ManyToManyField('director', related_name='movies', blank=True)

    tags = models.CharField(max_length=255, null=True, blank=True)

    description = models.TextField(null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"ID: {movie_id}, Title: {movie_title}"

class Actor(models.Model):

    actor_id = models.IntegerField(primary_key=True, unique=True)
    actor_name = models.CharField(max_length=255)

    def __str__(self):
        return f"ID: {actor_id}, Name: {actor_name}"
    
class director(models.Model):

    director_id = models.IntegerField(primary_key=True, unique=True)
    director_name = models.CharField(max_length=255)

    def __str__(self):
        return f"ID: {director_id}, Name: {director_name}"