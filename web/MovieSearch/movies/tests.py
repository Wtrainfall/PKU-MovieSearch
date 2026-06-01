from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Actor, Director, Movie, Segment


class HomeUrlTests(SimpleTestCase):
    def test_home_url_is_namespaced(self):
        self.assertEqual(reverse('movies:home'), '/')

    def test_homepage_renders_reversed_search_urls(self):
        response = self.client.get(reverse('movies:home'))
        self.assertContains(response, reverse('search:agent'))
        self.assertContains(response, reverse('movies:movie_detail', args=[0]))
        self.assertContains(response, 'cover-page')


class MovieDetailTests(TestCase):
    def setUp(self):
        self.movie = Movie.objects.create(
            movie_id=1,
            movie_title='楚门的世界',
            year=1998,
            genre='剧情, 科幻',
            tags='自由, 经典',
            description='楚门发现自己的生活被电视节目操控。',
            rating=9.3,
        )
        actor = Actor.objects.create(actor_name='Jim Carrey')
        director = Director.objects.create(director_name='Peter Weir')
        self.movie.actors.add(actor)
        self.movie.directors.add(director)
        Segment.objects.create(
            movie=self.movie,
            segment_order=1,
            summary_content='楚门在镜子前自言自语。',
            script_content='一面雾气朦胧的镜子。',
        )
        for index in range(2, 12):
            Segment.objects.create(
                movie=self.movie,
                segment_order=index,
                summary_content=f'第 {index} 个片段摘要。',
                script_content=f'第 {index} 个片段内容。',
            )

    def test_movie_detail_url_is_namespaced(self):
        self.assertEqual(reverse('movies:movie_detail', args=[1]), '/movies/1/')

    def test_movie_detail_renders_movie_data_from_database(self):
        response = self.client.get(reverse('movies:movie_detail', args=[1]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '楚门的世界')
        self.assertContains(response, 'Peter Weir')
        self.assertContains(response, 'Jim Carrey')
        self.assertContains(response, '楚门在镜子前自言自语。')
        self.assertContains(response, '一面雾气朦胧的镜子。')
        self.assertContains(response, '<details class="section segments-panel">', html=False)
        self.assertContains(response, '<summary>', html=False)
        self.assertContains(response, '当前显示第 1-10 条，共 11 条。')
        self.assertContains(response, '下一页')
        self.assertNotContains(response, '第 11 个片段摘要。')

    def test_movie_detail_paginates_segments(self):
        response = self.client.get(f"{reverse('movies:movie_detail', args=[1])}?page=2")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '当前显示第 11-11 条，共 11 条。')
        self.assertContains(response, '第 11 个片段摘要。')
        self.assertContains(response, '上一页')

    def test_movie_detail_returns_404_for_missing_movie(self):
        response = self.client.get(reverse('movies:movie_detail', args=[999]))

        self.assertEqual(response.status_code, 404)
