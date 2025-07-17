from content_ingestion.models import DocumentChunk, Topic, Subtopic

def classify_topic_and_difficulty():
    """
    Loops through DocumentChunk, matches topic/subtopic, and assigns difficulty.
    """
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

        #topic/subtopic titles into the chunk
        if matched_topic:
            chunk.topic_title = matched_topic.name

        if matched_subtopic:
            chunk.subtopic_title = matched_subtopic.name

       
        text_length = len(text)

        if text_length <= 50:
            difficulty = "Easy"
        elif text_length <= 100:
            difficulty = "Intermediate"
        else:
            difficulty = "Hard"

       
        chunk.parser_metadata['difficulty'] = difficulty

        chunk.save()

    return f"Processed {chunks.count()} document chunks."
