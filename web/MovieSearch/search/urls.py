from django.urls import path

from agent import views as agent_views

from . import views


app_name = 'search'


urlpatterns = [
    path('api/', views.search_api, name='api'),
    path('agent/', agent_views.agent_api, name='agent'),
    path('agent/stream/', agent_views.agent_stream_api, name='agent_stream'),
    path('stats/', views.stats_api, name='stats'),
]
