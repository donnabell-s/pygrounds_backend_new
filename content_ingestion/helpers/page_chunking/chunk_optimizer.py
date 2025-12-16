from typing import List, Dict, Any
import re
from content_ingestion.models import DocumentChunk

class ChunkOptimizer:
    # post-process chunks for llm + rag
    
    def __init__(self):
        self.section_patterns = {
            # order matters (most specific first)
            'challenge': re.compile(r'^(\d+\.\d+)\s*Challenge:\s*(.+?)(?:\s*[\.\s]*)?$'),
            'exercise': re.compile(r'^(\d+\.\d+)\s*(?:Review\s*)?Exercise(?:s)?:\s*(.+?)(?:\s*[\.\s]*)?$'),
            'subsection': re.compile(r'^(\d+\.\d+)\s*(.+?)(?:\s*[\.\s]*)?$'),
            'chapter': re.compile(r'^(\d+)\s*(.+?)(?:\s*[\.\s]*)?$'),
        }
        
        # cleanup regexes (urls, page numbers, whitespace, dot leaders)
        self.cleanup_patterns = [
            (re.compile(r'\n{3,}'), '\n\n'),
            (re.compile(r'\.{3,}'), ''),
            (re.compile(r'\s+'), ' '),
            (re.compile(r'^\s+|\s+$', re.MULTILINE), ''),
            (re.compile(r'https?://[^\s]+'), ''),
            (re.compile(r'www\.[^\s]+'), ''),
            (re.compile(r'\S+\.com[^\s]*'), ''),
            (re.compile(r'realpython\.com[^\s]*'), ''),
            (re.compile(r'\s+\d{1,3}\s*$', re.MULTILINE), ''),
            (re.compile(r'^\s*\d{1,3}\s*$', re.MULTILINE), ''),
            (re.compile(r'\s+\d{1,3}\s*\n'), '\n'),
        ]
    
    def optimize_chunks(self, document_id: int) -> Dict[str, Any]:
        # optimize all chunks for a doc
        chunks = DocumentChunk.objects.filter(document_id=document_id).order_by('page_number', 'order_in_doc')
        
        optimized_chunks = []
        stats = {
            'total_chunks': 0,
            'optimized_chunks': 0,
            'title_fixes': 0,
            'content_improvements': 0,
            'structure_enhancements': 0
        }
        
        print(f"\nOPTIMIZING CHUNKS FOR LLM CONSUMPTION")
        print(f"{'='*60}")
        
        for chunk in chunks:
            try:
                optimized = self._optimize_single_chunk(chunk)
                optimized_chunks.append(optimized)
                stats['total_chunks'] += 1
                
                if optimized['title_cleaned']:
                    stats['title_fixes'] += 1
                if optimized['content_improved']:
                    stats['content_improvements'] += 1
                if optimized['structure_enhanced']:
                    stats['structure_enhancements'] += 1
                    
                stats['optimized_chunks'] += 1
                
                print(f"OK: Chunk {chunk.id}: {optimized['clean_title'][:50]}...")
                
            except Exception as e:
                print(f"ERROR: Error optimizing chunk {chunk.id}: {str(e)}")
                # fallback to original if optimization fails
                optimized_chunks.append(self._fallback_chunk_format(chunk))
                stats['total_chunks'] += 1
        
        return {
            'optimized_chunks': optimized_chunks,
            'optimization_stats': stats,
            'llm_ready_format': self._create_llm_format(optimized_chunks)
        }
    
    def _optimize_single_chunk(self, chunk: DocumentChunk) -> Dict[str, Any]:
        # optimize one chunk
        clean_title, title_section = self._extract_clean_title(chunk.subtopic_title)
        
        clean_content = self._clean_content(chunk.text)
        
        content_section = self._extract_section_from_content(clean_content)
        
        final_title = content_section if content_section else clean_title
        
        structured_content = self._structure_content(clean_content, final_title)
        
        concepts = self._extract_concepts(structured_content)
        
        code_examples = self._extract_code_examples(structured_content)
        exercises = self._extract_exercises(structured_content)
        
        return {
            'id': chunk.id,
            'clean_title': final_title,
            'content_type': self._categorize_content(structured_content),
            'concepts': ' '.join(concepts[:6]),
            'code_examples_count': len(code_examples),
            'exercises_count': len(exercises),
    
            'llm_context': self._create_llm_context(clean_content),
            
            'page_number': chunk.page_number + 1,
            'section_number': title_section,
            'text_length': len(clean_content),
            'rag_keywords': self._extract_rag_keywords(final_title, structured_content)[:8],
            
            # flags
            'title_cleaned': True,
            'content_improved': len(self._clean_content(chunk.text)) != len(chunk.text),
            'structure_enhanced': True,
        }
    
    def _extract_clean_title(self, title: str) -> tuple[str, str]:
        # clean toc title + extract section number
        title = title.strip()
        
        for pattern_name, pattern in self.section_patterns.items():
            match = pattern.match(title)
            if match:
                if pattern_name == 'challenge':
                    section_num = match.group(1)
                    clean_title = f"Challenge: {match.group(2).strip()}"
                elif pattern_name == 'exercise':
                    section_num = match.group(1)
                    clean_title = f"Exercises: {match.group(2).strip()}"
                else:
                    section_num = match.group(1)
                    clean_title = match.group(2).strip()
                
                # final cleanup
                clean_title = re.sub(r'[\.\s]*\.[\.\s]*', '', clean_title)
                clean_title = re.sub(r'[\.\s]+$', '', clean_title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                
                return clean_title, section_num
        
        # fallback cleanup
        clean = title
        
        clean = re.sub(r'^\.?\d+(\.\d+)?\.?\s*', '', clean)
        
        clean = re.sub(r'[\.\s]*\.[\.\s]*', '', clean)
        
        clean = re.sub(r'[\.\s]+$', '', clean)
        
        clean = re.sub(r'\s+', ' ', clean)
        
        return clean.strip(), ""
    
    def _clean_content(self, text: str) -> str:
        content = text
        
        for pattern, replacement in self.cleanup_patterns:
            content = pattern.sub(replacement, content)
        
        return content.strip()
    
    def _extract_section_from_content(self, content: str) -> str:
        # try to infer a better title from content
        lines = content.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if not line:
                continue
                
            if re.match(r'^\d+\.\d*\s*[A-Z]', line):
                clean = re.sub(r'\s*\d+\s*$', '', line)
                return clean.strip()
        
        return ""
    
    def _structure_content(self, content: str, title: str) -> str:
        # normalize content blocks for analysis 
        paragraphs = content.split('\n\n')
        structured_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # skip toc-ish junk
            if re.match(r'^\d+(\.\d+)?\s*$', para):
                continue
            if re.match(r'^\d+(\.\d+)?\s+[A-Z].*\.{3,}', para):
                continue
            
            if re.match(r'^\d{1,3}$', para):
                continue
                
            para = re.sub(r'\s+\d{1,3}$', '', para)
                
            if '>>>' in para or para.startswith('    '):
                structured_paragraphs.append(f"```python\n{para}\n```")
            elif re.match(r'^\d+\.\s', para):
                structured_paragraphs.append(f"**Exercise {para[0]}:** {para[2:]}")
            else:
                structured_paragraphs.append(para)
        
        return '\n\n'.join(structured_paragraphs)
    
    def _categorize_content(self, content: str) -> str:
        # quick content bucket
        content_lower = content.lower()
        
        if 'challenge' in content_lower:
            return 'challenge'
        elif 'exercise' in content_lower or 'review exercise' in content_lower:
            return 'exercises'
        elif '>>>' in content or 'python' in content_lower:
            return 'tutorial_with_code'
        elif 'method' in content_lower or 'function' in content_lower:
            return 'concept_explanation'
        else:
            return 'instructional_text'
    
    def _extract_concepts(self, content: str) -> List[str]:
        concepts = []
        content_lower = content.lower()
        
        programming_terms = [
            'input()', 'print()', 'string', 'variable', 'method', 'function',
            'uppercase', 'lowercase', 'concatenation', 'indexing', 'slicing',
            'loop', 'if statement', 'else', 'while', 'for', 'list', 'dictionary',
            'tuple', 'class', 'object', 'module', 'package', 'import'
        ]
        
        for term in programming_terms:
            if term.lower() in content_lower:
                concepts.append(term)
        
        return list(set(concepts))
    
    def _extract_learning_objectives(self, content: str) -> List[str]:
        objectives = []
        
        objective_patterns = [
            r"you'll learn (?:how )?to (.+?)(?:\.|$)",
            r"this section (?:will )?(?:teach|show) (?:you )?(?:how )?to (.+?)(?:\.|$)",
            r"learn (?:how )?to (.+?)(?:\.|$)"
        ]
        
        content_lower = content.lower()
        for pattern in objective_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            objectives.extend([match.strip() for match in matches])
        
        return objectives[:3]
    
    def _extract_code_examples(self, content: str) -> List[str]:
        code_blocks = []
        
        code_patterns = [
            r'```python\n(.*?)\n```',
            r'>>> (.+?)(?:\n|$)',
            r'(?:^|\n)([a-zA-Z_][a-zA-Z0-9_]*\s*=.*?)(?:\n|$)'
        ]
        
        for pattern in code_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
            code_blocks.extend([match.strip() for match in matches if match.strip()])
        
        return code_blocks[:5]
    
    def _extract_exercises(self, content: str) -> List[str]:
        exercises = []
        
        exercise_pattern = r'(?:^|\n)\s*(\d+\.\s*.+?)(?=\n\s*\d+\.|$)'
        matches = re.findall(exercise_pattern, content, re.DOTALL)
        
        for match in matches:
            exercise = match.strip()
            if len(exercise) > 20:
                exercises.append(exercise)
        
        return exercises
    
    def _create_llm_context(self, content: str) -> str:
        clean_content = content
        
        clean_content = re.sub(r'^\d+(\.\d+)?\s+[A-Z].*?\n\n', '', clean_content, flags=re.MULTILINE)
        
        return f"""
CONTENT:
{clean_content}

KEY LEARNING POINTS:
- Interactive programming concepts
- String manipulation techniques  
- Practical coding exercises
- Development environment usage
        """.strip()
    
    def _extract_rag_keywords(self, title: str, content: str) -> List[str]:
        keywords = []
        
        title_words = re.findall(r'\b[A-Za-z]{3,}\b', title.lower())
        keywords.extend(title_words)
        
        tech_terms = re.findall(r'\b(?:python|input|string|method|function|variable|print|user|interactive|programming|code|exercise)\b', content.lower())
        keywords.extend(tech_terms)
        
        return list(set(keywords))
    
    def _assess_difficulty(self, content: str) -> str:
        # neutral for now
        return 'info'
    
    def _extract_prerequisites(self, content: str) -> List[str]:
        prereqs = []
        content_lower = content.lower()
        
        if 'string' in content_lower:
            prereqs.append('Basic string knowledge')
        if 'variable' in content_lower:
            prereqs.append('Variable assignment')
        if 'function' in content_lower or 'method' in content_lower:
            prereqs.append('Function concepts')
        
        return prereqs
    
    def _create_llm_format(self, optimized_chunks: List[Dict]) -> List[Dict]:
        llm_chunks = []
        
        for chunk in optimized_chunks:
            llm_chunk = {
                'id': f"chunk_{chunk['id']}",
                'title': chunk['clean_title'],
                'content': chunk['llm_context'],
                'page': chunk['page_number'],
                'type': chunk['content_type'],
                'concepts': chunk['concepts'],
                'keywords': chunk['rag_keywords'],
                'code_examples_count': chunk['code_examples_count'],
                'exercises_count': chunk['exercises_count'],
             
                'metadata': {
                    'text_length': chunk['text_length'],
                    'optimized': True,
                    'source': 'toc_chunk_processor'
                }
            }
            llm_chunks.append(llm_chunk)
        
        return llm_chunks
    
    def _fallback_chunk_format(self, chunk: DocumentChunk) -> Dict[str, Any]:
        # fallback
        return {
            'id': chunk.id,
            'original_title': chunk.subtopic_title,
            'clean_title': chunk.subtopic_title,
            'section_number': '',
            'page_number': chunk.page_number + 1,
            'content_type': 'text',
            'concepts': '',
            'code_examples_count': 0,
            'exercises_count': 0,
            'text_length': len(chunk.text),
            'llm_context': chunk.text[:500] + '...' if len(chunk.text) > 500 else chunk.text,
            'rag_keywords': [],
            'title_cleaned': False,
            'content_improved': False,
            'structure_enhanced': False,
        }
