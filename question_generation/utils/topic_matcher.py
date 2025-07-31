from content_ingestion.models import DocumentChunk, Topic, Subtopic
from .difficulty_predictor import predict_difficulty 

def classify_topic_and_difficulty():
    topics = Topic.objects.all()
    subtopics = Subtopic.objects.all()
    chunks = DocumentChunk.objects.all()

    for chunk in chunks:
        text = chunk.text.lower()

        matched_topic = None
        matched_subtopic = None

        for topic in topics:
            if topic.name.lower() in text:
                matched_topic = topic
                break

        for subtopic in subtopics:
            if subtopic.name.lower() in text:
                matched_subtopic = subtopic
                break

        if matched_topic:
            chunk.topic_title = matched_topic.name
        if matched_subtopic:
            chunk.subtopic_title = matched_subtopic.name

        predicted_difficulty = predict_difficulty(text)

        chunk.parser_metadata['difficulty'] = predicted_difficulty

        chunk.save()

    return f"Processed {chunks.count()} document chunks with topic/subtopic/difficulty."
