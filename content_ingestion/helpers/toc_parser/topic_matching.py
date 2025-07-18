import re
from typing import List, Dict, Tuple, Set
from difflib import SequenceMatcher
from content_ingestion.models import Topic, Subtopic, TOCEntry, ContentMapping

class FastTopicMatcher:
    """
    Fast keyword-based topic matching system that avoids heavy NLP computations.
    Uses string similarity, keyword matching, and caching for performance.
    """
    def __init__(self):
        # Cache for preprocessed topic data
        self._topic_cache = None
        self._subtopic_cache = None
        
    def _preprocess_text(self, text: str) -> Set[str]:
        """Convert text to normalized keyword set, optimized for speed"""
        words = re.findall(r'\b\w+\b', text.lower())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
        return {word for word in words if len(word) > 2 and word not in stop_words}
    
    def _get_topic_cache(self):
        """Build and cache topic data for fast lookups, skip meta/intro topics"""
        if self._topic_cache is None:
            self._topic_cache = []
            meta_titles = {'foreword', 'preface', 'introduction', 'why this book', 'about', 'acknowledgments', 'contents', 'table of contents', 'toc', 'index'}
            for topic in Topic.objects.all():
                title_lower = topic.name.lower().strip()
                if any(meta in title_lower for meta in meta_titles):
                    continue
                keywords = self._preprocess_text(f"{topic.name} {topic.description}")
                self._topic_cache.append({
                    'topic': topic,
                    'keywords': keywords,
                    'name_keywords': self._preprocess_text(topic.name)
                })
        return self._topic_cache
    
    def _get_subtopic_cache(self):
        """Build and cache subtopic data for fast lookups, skip meta/intro subtopics"""
        if self._subtopic_cache is None:
            self._subtopic_cache = []
            meta_titles = {'foreword', 'preface', 'introduction', 'why this book', 'about', 'acknowledgments', 'contents', 'table of contents', 'toc', 'index'}
            for subtopic in Subtopic.objects.all():
                title_lower = subtopic.name.lower().strip()
                if any(meta in title_lower for meta in meta_titles):
                    continue
                keywords = self._preprocess_text(f"{subtopic.name} {subtopic.description}")
                self._subtopic_cache.append({
                    'subtopic': subtopic,
                    'keywords': keywords,
                    'name_keywords': self._preprocess_text(subtopic.name)
                })
        return self._subtopic_cache
    
    def calculate_fast_similarity(self, text1: str, text2: str) -> float:
        """Fast similarity calculation using string matching"""
        # Use SequenceMatcher for basic string similarity
        similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        return similarity
    
    def calculate_keyword_similarity(self, title_keywords: Set[str], target_keywords: Set[str], name_keywords: Set[str]) -> float:
        """Calculate similarity based on keyword overlap"""
        if not title_keywords or not target_keywords:
            return 0.0
        
        # Calculate intersection ratios
        common_keywords = title_keywords.intersection(target_keywords)
        name_overlap = title_keywords.intersection(name_keywords)
        
        # Weight name matches higher
        name_similarity = len(name_overlap) / len(name_keywords) if name_keywords else 0
        general_similarity = len(common_keywords) / len(title_keywords.union(target_keywords))
        
        # Combine similarities with weights
        return (name_similarity * 0.7) + (general_similarity * 0.3)
    
    def find_best_topic_match(self, title: str) -> Tuple[Topic, float]:
        """Find the most similar topic using fast keyword matching, skip meta/intro titles"""
        title_keywords = self._preprocess_text(title)
        meta_titles = {'foreword', 'preface', 'introduction', 'why this book', 'about', 'acknowledgments', 'contents', 'table of contents', 'toc', 'index'}
        if any(meta in title.lower().strip() for meta in meta_titles):
            return None, 0.0
        topic_cache = self._get_topic_cache()
        max_similarity = 0
        best_topic = None
        for topic_data in topic_cache:
            keyword_sim = self.calculate_keyword_similarity(
                title_keywords,
                topic_data['keywords'],
                topic_data['name_keywords']
            )
            if keyword_sim == 0:
                keyword_sim = self.calculate_fast_similarity(title, topic_data['topic'].name) * 0.5
            if keyword_sim > max_similarity:
                max_similarity = keyword_sim
                best_topic = topic_data['topic']
        return best_topic, max_similarity
    
    def find_best_subtopic_match(self, title: str) -> Tuple[Subtopic, float]:
        """Find the most similar subtopic using fast keyword matching, skip meta/intro titles"""
        title_keywords = self._preprocess_text(title)
        meta_titles = {'foreword', 'preface', 'introduction', 'why this book', 'about', 'acknowledgments', 'contents', 'table of contents', 'toc', 'index'}
        if any(meta in title.lower().strip() for meta in meta_titles):
            return None, 0.0
        subtopic_cache = self._get_subtopic_cache()
        max_similarity = 0
        best_subtopic = None
        for subtopic_data in subtopic_cache:
            keyword_sim = self.calculate_keyword_similarity(
                title_keywords,
                subtopic_data['keywords'],
                subtopic_data['name_keywords']
            )
            if keyword_sim == 0:
                keyword_sim = self.calculate_fast_similarity(title, subtopic_data['subtopic'].name) * 0.5
            if keyword_sim > max_similarity:
                max_similarity = keyword_sim
                best_subtopic = subtopic_data['subtopic']
        return best_subtopic, max_similarity

    def create_content_mapping(self, toc_entry: TOCEntry, min_confidence: float = 0.2) -> Dict:
        """
        Create content mapping for a TOC entry using fast keyword matching.
        Skips meta/intro entries and optimizes for speed.
        """
        mapping_data = {
            'toc_entry': toc_entry,
            'confidence_score': 0.0,
            'mapping_metadata': {}
        }
        meta_titles = {'foreword', 'preface', 'introduction', 'why this book', 'about', 'acknowledgments', 'contents', 'table of contents', 'toc', 'index'}
        if any(meta in toc_entry.title.lower().strip() for meta in meta_titles):
            mapping_data['mapping_metadata'] = {
                'skipped': True,
                'reason': 'meta/intro section',
                'original_title': toc_entry.title
            }
            return mapping_data
        # Try subtopic matching first (more specific)
        best_subtopic, subtopic_similarity = self.find_best_subtopic_match(toc_entry.title)
        if best_subtopic and subtopic_similarity >= min_confidence:
            mapping_data['subtopic'] = best_subtopic
            mapping_data['topic'] = best_subtopic.topic
            mapping_data['zone'] = best_subtopic.topic.zone
            mapping_data['confidence_score'] = subtopic_similarity
            mapping_data['mapping_metadata'] = {
                'subtopic_similarity': subtopic_similarity,
                'matched_by': 'fast_keyword_subtopic',
                'original_title': toc_entry.title
            }
        else:
            # Fallback to topic matching
            best_topic, topic_similarity = self.find_best_topic_match(toc_entry.title)
            if best_topic and topic_similarity >= min_confidence:
                mapping_data['topic'] = best_topic
                mapping_data['zone'] = best_topic.zone
                mapping_data['confidence_score'] = topic_similarity
                mapping_data['mapping_metadata'] = {
                    'topic_similarity': topic_similarity,
                    'matched_by': 'fast_keyword_topic',
                    'original_title': toc_entry.title
                }
        # No debug prints for speed
        return mapping_data

# Legacy class for backwards compatibility (but recommend using FastTopicMatcher)
class TopicMatcher(FastTopicMatcher):
    """Legacy NLP-based matcher - now redirects to FastTopicMatcher for performance"""
    def __init__(self):
        print("[INFO] Using fast keyword-based matching instead of NLP for better performance")
        super().__init__()
