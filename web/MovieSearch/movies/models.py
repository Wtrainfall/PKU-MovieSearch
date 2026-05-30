from django.db import models

# Create your models here.
class Movie(models.Model):

    #base fields
    movie_id = models.IntegerField(primary_key=True, unique=True)
    movie_title = models.CharField(max_length=255)
    year = models.IntegerField(null=True, blank=True)
    genre = models.CharField(max_length=255, null=True, blank=True)

    actors = models.ManyToManyField('Actor', related_name='movies', blank=True)
    directors = models.ManyToManyField('Director', related_name='movies', blank=True)

    tags = models.CharField(max_length=255, null=True, blank=True)

    description = models.TextField(null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"ID: {self.movie_id}, Title: {self.movie_title}"

class Actor(models.Model):

    actor_id = models.AutoField(primary_key=True, unique=True)
    actor_name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"ID: {self.actor_id}, Name: {self.actor_name}"
    
class Director(models.Model):

    director_id = models.AutoField(primary_key=True, unique=True)
    director_name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"ID: {self.director_id}, Name: {self.director_name}"

class Segment(models.Model):

    segment_id = models.AutoField(primary_key=True, unique=True)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='segments')
    script_content = models.TextField(null=True, blank=True)
    summary_content = models.TextField(null=True, blank=True)
    segment_order = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"ID: {self.segment_id}, Movie: {self.movie.movie_title}, Content: {self.script_content[:100]}"
