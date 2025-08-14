from reading.views import TopicTOC

urlpatterns += [
    path("api/topics/<str:topic_name>/toc/", TopicTOC.as_view(), name="topic-toc"),
]
