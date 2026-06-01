from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Movie

def home(request):
    return render(request, 'homepage/home_v2.html')


def movie_detail(request, movie_id):
    movie = get_object_or_404(
        Movie.objects.prefetch_related('actors', 'directors'),
        movie_id=movie_id,
    )
    segment_queryset = movie.segments.order_by('segment_order', 'segment_id')
    paginator = Paginator(segment_queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'movies/detail.html',
        {
            'movie': movie,
            'segments': page_obj.object_list,
            'page_obj': page_obj,
            'segment_count': paginator.count,
        },
    )
