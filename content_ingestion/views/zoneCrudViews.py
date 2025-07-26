"""
Game zone, topic, and subtopic CRUD operations.
"""

from .imports import *

class GameZoneListCreateView(generics.ListCreateAPIView):
    """
    List all game zones or create a new zone
    """
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class GameZoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a game zone
    """
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class TopicListCreateView(generics.ListCreateAPIView):
    """
    List all topics or create a new topic
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class TopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a topic
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class ZoneTopicsView(generics.ListAPIView):
    """
    List all topics for a specific zone
    """
    serializer_class = TopicSerializer

    def get_queryset(self):
        zone_id = self.kwargs['zone_id']
        return Topic.objects.filter(zone_id=zone_id)

class SubtopicListCreateView(generics.ListCreateAPIView):
    """
    List all subtopics or create a new subtopic
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

class SubtopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a subtopic
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

class TopicSubtopicsView(generics.ListAPIView):
    """
    List all subtopics for a specific topic
    """
    serializer_class = SubtopicSerializer

    def get_queryset(self):
        topic_id = self.kwargs['topic_id']
        return Subtopic.objects.filter(topic_id=topic_id)