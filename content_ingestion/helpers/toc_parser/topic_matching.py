import spacy
from typing import List, Dict, Tuple
from ..models import Topic, Subtopic, TOCEntry, ContentMapping

class TopicMatcher:
    """
    Uses NLP to match TOC entries with topics and subtopics based on semantic similarity
    """
    def __init__(self):
        # Load English language model - using medium size for better accuracy
        # Install with: python -m spacy download en_core_web_md
        self.nlp = spacy.load("en_core_web_md")
        
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        doc1 = self.nlp(text1.lower())
        doc2 = self.nlp(text2.lower())
        return doc1.similarity(doc2)
    
    def find_best_topic_match(self, title: str, topics: List[Topic]) -> Tuple[Topic, float]:
        """Find the most similar topic for a given title"""
        max_similarity = 0
        best_topic = None
        
        for topic in topics:
            # Compare with topic name and description
            name_sim = self.calculate_similarity(title, topic.name)
            desc_sim = self.calculate_similarity(title, topic.description)
            similarity = max(name_sim, desc_sim)
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_topic = topic
                
        return best_topic, max_similarity
    
    def find_best_subtopic_match(self, title: str, subtopics: List[Subtopic]) -> Tuple[Subtopic, float]:
        """Find the most similar subtopic for a given title"""
        max_similarity = 0
        best_subtopic = None
        
        for subtopic in subtopics:
            # Compare with subtopic name and description
            name_sim = self.calculate_similarity(title, subtopic.name)
            desc_sim = self.calculate_similarity(title, subtopic.description)
            similarity = max(name_sim, desc_sim)
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_subtopic = subtopic
                
        return best_subtopic, max_similarity
    
    def create_content_mapping(self, toc_entry: TOCEntry, min_confidence: float = 0.3) -> Dict:
        """
        Create content mapping for a TOC entry based on similarity matching.
        Focus on subtopic-level matching for more granular content organization.
        
        Args:
            toc_entry: TOCEntry to map
            min_confidence: Minimum similarity score to consider a match (lowered for more matches)
            
        Returns:
            Dictionary with mapping details
        """
        # Get all subtopics for direct matching (more granular than topics)
        subtopics = Subtopic.objects.all()
        mapping_data = {
            'toc_entry': toc_entry,
            'confidence_score': 0.0,
            'mapping_metadata': {}
        }
        
        # Find best subtopic match first (more specific)
        best_subtopic, subtopic_similarity = self.find_best_subtopic_match(toc_entry.title, subtopics)
        
        if best_subtopic and subtopic_similarity >= min_confidence:
            mapping_data['subtopic'] = best_subtopic
            mapping_data['topic'] = best_subtopic.topic
            mapping_data['zone'] = best_subtopic.topic.zone
            mapping_data['confidence_score'] = subtopic_similarity
            
            # Store similarity scores in metadata
            mapping_data['mapping_metadata'] = {
                'subtopic_similarity': subtopic_similarity,
                'matched_by': 'nlp_subtopic_similarity',
                'original_title': toc_entry.title
            }
        else:
            # Fallback to topic matching if no good subtopic match
            topics = Topic.objects.all()
            best_topic, topic_similarity = self.find_best_topic_match(toc_entry.title, topics)
            
            if best_topic and topic_similarity >= min_confidence:
                mapping_data['topic'] = best_topic
                mapping_data['zone'] = best_topic.zone
                mapping_data['confidence_score'] = topic_similarity
                
                mapping_data['mapping_metadata'] = {
                    'topic_similarity': topic_similarity,
                    'matched_by': 'nlp_topic_similarity',
                    'original_title': toc_entry.title
                }
        
        print(f"[DEBUG] Mapping for '{toc_entry.title}':")
        if 'subtopic' in mapping_data:
            print(f"  Subtopic: {mapping_data['subtopic'].name} ({subtopic_similarity:.2f})")
        elif 'topic' in mapping_data:
            print(f"  Topic: {mapping_data['topic'].name} ({mapping_data['confidence_score']:.2f})")
        else:
            print(f"  No match found (best score: {mapping_data['confidence_score']:.2f})")
        
        return mapping_data
