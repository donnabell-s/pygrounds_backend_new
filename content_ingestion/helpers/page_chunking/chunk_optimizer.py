from typing import List, Dict, Any
import re
from content_ingestion.models import DocumentChunk

class ChunkOptimizer:
    # Post-process chunks to optimize them for LLM consumption and RAG applications.
    
    def __init__(self):
        self.section_patterns = {
            # Order matters - more specific patterns first
            'challenge': re.compile(r'^(\d+\.\d+)\s*Challenge:\s*(.+?)(?:\s*[\.\s]*)?$'),
            'exercise': re.compile(r'^(\d+\.\d+)\s*(?:Review\s*)?Exercise(?:s)?:\s*(.+?)(?:\s*[\.\s]*)?$'),
            'subsection': re.compile(r'^(\d+\.\d+)\s*(.+?)(?:\s*[\.\s]*)?$'),
            'chapter': re.compile(r'^(\d+)\s*(.+?)(?:\s*[\.\s]*)?$'),
        }
        
        # Text cleaning patterns
        self.cleanup_patterns = [
            (re.compile(r'\n{3,}'), '\n\n'),  # Multiple newlines
            (re.compile(r'\.{3,}'), ''),      # Dot leaders
            (re.compile(r'\s+'), ' '),        # Multiple spaces
            (re.compile(r'^\s+|\s+$', re.MULTILINE), ''),  # Leading/trailing whitespace
            # Remove URLs and links
            (re.compile(r'https?://[^\s]+'), ''),  # HTTP/HTTPS URLs
            (re.compile(r'www\.[^\s]+'), ''),       # www links
            (re.compile(r'\S+\.com[^\s]*'), ''),    # .com domains
            (re.compile(r'realpython\.com[^\s]*'), ''),  # Specific realpython links
            # Remove page numbers (standalone numbers at end of lines/content)
            (re.compile(r'\s+\d{1,3}\s*$', re.MULTILINE), ''),  # Page numbers at end of lines
            (re.compile(r'^\s*\d{1,3}\s*$', re.MULTILINE), ''),  # Standalone page numbers
            (re.compile(r'\s+\d{1,3}\s*\n'), '\n'),  # Page numbers before newlines
        ]
    
    def optimize_chunks(self, document_id: int) -> Dict[str, Any]:
        # Optimize all chunks for a document for better LLM consumption.
        chunks = DocumentChunk.objects.filter(document_id=document_id).order_by('page_number', 'order_in_doc')
        
        optimized_chunks = []
        stats = {
            'total_chunks': 0,
            'optimized_chunks': 0,
            'title_fixes': 0,
            'content_improvements': 0,
            'structure_enhancements': 0
        }
        
        print(f"\n🔧 OPTIMIZING CHUNKS FOR LLM CONSUMPTION")
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
                
                print(f"✅ Chunk {chunk.id}: {optimized['clean_title'][:50]}...")
                
            except Exception as e:
                print(f"❌ Error optimizing chunk {chunk.id}: {str(e)}")
                # Include original chunk if optimization fails
                optimized_chunks.append(self._fallback_chunk_format(chunk))
                stats['total_chunks'] += 1
        
        return {
            'optimized_chunks': optimized_chunks,
            'optimization_stats': stats,
            'llm_ready_format': self._create_llm_format(optimized_chunks)
        }
    
    def _optimize_single_chunk(self, chunk: DocumentChunk) -> Dict[str, Any]:
        # Optimize a single chunk for LLM consumption.
        # Extract clean title
        clean_title, title_section = self._extract_clean_title(chunk.subtopic_title)
        
        # Clean and structure content
        clean_content = self._clean_content(chunk.text)
        
        # Extract actual section from content if possible
        content_section = self._extract_section_from_content(clean_content)
        
        # Determine best title (from content or TOC)
        final_title = content_section if content_section else clean_title
        
        # Structure content for analysis (but don't include in output)
        structured_content = self._structure_content(clean_content, final_title)
        
        # Extract key concepts
        concepts = self._extract_concepts(structured_content)
        
        # Extract code examples and exercises
        code_examples = self._extract_code_examples(structured_content)
        exercises = self._extract_exercises(structured_content)
        
        return {
            'id': chunk.id,
            'clean_title': final_title,
            'content_type': self._categorize_content(structured_content),
            'concepts': ' '.join(concepts[:6]),  # Join concepts as string for brevity
            'code_examples_count': len(code_examples),
            'exercises_count': len(exercises),
            # 'structured_content': structured_content,  # REMOVED - too verbose
            'llm_context': self._create_llm_context(clean_content),  # Remove title from context
            
            # Additional metadata for advanced use (kept minimal)
            'page_number': chunk.page_number + 1,
            'section_number': title_section,
            'text_length': len(clean_content),  # Use clean_content length instead of structured
            'rag_keywords': self._extract_rag_keywords(final_title, structured_content)[:8],  # Limit keywords
            
            # Optimization flags
            'title_cleaned': True,
            'content_improved': len(self._clean_content(chunk.text)) != len(chunk.text),
            'structure_enhanced': True,
        }
    
    def _extract_clean_title(self, title: str) -> tuple[str, str]:
        # Extract clean title and section number from TOC title.
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
                
                # Post-process to remove any remaining dots and cleanup
                clean_title = re.sub(r'[\.\s]*\.[\.\s]*', '', clean_title)
                clean_title = re.sub(r'[\.\s]+$', '', clean_title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                
                return clean_title, section_num
        
        # Enhanced fallback: remove dots, section numbers, and clean thoroughly
        clean = title
        
        # Remove section numbers at start (e.g., "4.4 " or ".4 " or "4.4. ")
        clean = re.sub(r'^\.?\d+(\.\d+)?\.?\s*', '', clean)
        
        # Remove dot patterns (e.g., ". . . . . . . . . . . . . .")
        clean = re.sub(r'[\.\s]*\.[\.\s]*', '', clean)
        
        # Remove trailing dots and spaces
        clean = re.sub(r'[\.\s]+$', '', clean)
        
        # Clean up multiple spaces
        clean = re.sub(r'\s+', ' ', clean)
        
        return clean.strip(), ""
    
    def _clean_content(self, text: str) -> str:
        # Clean and normalize text content.
        content = text
        
        for pattern, replacement in self.cleanup_patterns:
            content = pattern.sub(replacement, content)
        
        return content.strip()
    
    def _extract_section_from_content(self, content: str) -> str:
        # Extract section title from the actual content.
        lines = content.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if not line:
                continue
                
            # Look for section headers
            if re.match(r'^\d+\.\d*\s*[A-Z]', line):
                # Remove any trailing dots or numbers
                clean = re.sub(r'\s*\d+\s*$', '', line)
                return clean.strip()
        
        return ""
    
    def _structure_content(self, content: str, title: str) -> str:
        # Structure content with headers/formatting.
        # Clean content without adding title headers
        paragraphs = content.split('\n\n')
        structured_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # Skip lines that are just section numbers or TOC titles
            if re.match(r'^\d+(\.\d+)?\s*$', para):
                continue
            if re.match(r'^\d+(\.\d+)?\s+[A-Z].*\.{3,}', para):
                continue
            
            # Skip standalone page numbers (1-3 digits only)
            if re.match(r'^\d{1,3}$', para):
                continue
                
            # Clean trailing page numbers from paragraphs
            para = re.sub(r'\s+\d{1,3}$', '', para)
                
            # Identify code blocks
            if '>>>' in para or para.startswith('    '):
                structured_paragraphs.append(f"```python\n{para}\n```")
            # Identify exercises
            elif re.match(r'^\d+\.\s', para):
                structured_paragraphs.append(f"**Exercise {para[0]}:** {para[2:]}")
            else:
                structured_paragraphs.append(para)
        
        return '\n\n'.join(structured_paragraphs)
    
    def _categorize_content(self, content: str) -> str:
        # Categorize the type of content.
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
        # Extract key programming concepts from content.
        concepts = []
        content_lower = content.lower()
        
        # Programming concepts
        programming_terms = [
            'input()', 'print()', 'string', 'variable', 'method', 'function',
            'uppercase', 'lowercase', 'concatenation', 'indexing', 'slicing',
            'loop', 'if statement', 'else', 'while', 'for', 'list', 'dictionary',
            'tuple', 'class', 'object', 'module', 'package', 'import'
        ]
        
        for term in programming_terms:
            if term.lower() in content_lower:
                concepts.append(term)
        
        return list(set(concepts))  # Remove duplicates
    
    def _extract_learning_objectives(self, content: str) -> List[str]:
        # Extract learning objectives from content.
        objectives = []
        
        # Look for objective indicators
        objective_patterns = [
            r"you'll learn (?:how )?to (.+?)(?:\.|$)",
            r"this section (?:will )?(?:teach|show) (?:you )?(?:how )?to (.+?)(?:\.|$)",
            r"learn (?:how )?to (.+?)(?:\.|$)"
        ]
        
        content_lower = content.lower()
        for pattern in objective_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            objectives.extend([match.strip() for match in matches])
        
        return objectives[:3]  # Limit to top 3
    
    def _extract_code_examples(self, content: str) -> List[str]:
        # Extract code examples from content.
        code_blocks = []
        
        # Find Python code patterns
        code_patterns = [
            r'```python\n(.*?)\n```',
            r'>>> (.+?)(?:\n|$)',
            r'(?:^|\n)([a-zA-Z_][a-zA-Z0-9_]*\s*=.*?)(?:\n|$)'
        ]
        
        for pattern in code_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
            code_blocks.extend([match.strip() for match in matches if match.strip()])
        
        return code_blocks[:5]  # Limit to top 5
    
    def _extract_exercises(self, content: str) -> List[str]:
        # Extract exercise descriptions from content.
        exercises = []
        
        # Find numbered exercises
        exercise_pattern = r'(?:^|\n)\s*(\d+\.\s*.+?)(?=\n\s*\d+\.|$)'
        matches = re.findall(exercise_pattern, content, re.DOTALL)
        
        for match in matches:
            exercise = match.strip()
            if len(exercise) > 20:  # Filter out short matches
                exercises.append(exercise)
        
        return exercises
    
    def _create_llm_context(self, content: str) -> str:
        # Create optimized context for LLM consumption without titles.
        # Clean content and remove any remaining section headers
        clean_content = content
        
        # Remove section number patterns at the start
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
        # Extract keywords for RAG retrieval optimization.
        keywords = []
        
        # Add title words
        title_words = re.findall(r'\b[A-Za-z]{3,}\b', title.lower())
        keywords.extend(title_words)
        
        # Add technical terms
        tech_terms = re.findall(r'\b(?:python|input|string|method|function|variable|print|user|interactive|programming|code|exercise)\b', content.lower())
        keywords.extend(tech_terms)
        
        return list(set(keywords))  # Remove duplicates
    
    def _assess_difficulty(self, content: str) -> str:
        # Assess content difficulty level (currently neutral).
        return 'info'  # Neutral level for LLM inspiration
    
    def _extract_prerequisites(self, content: str) -> List[str]:
        # Extract prerequisite knowledge from content.
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
        # Create final LLM-optimized format.
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
                # Removed verbose fields: code_examples, exercises, learning_objectives
                'metadata': {
                    'text_length': chunk['text_length'],
                    'optimized': True,
                    'source': 'toc_chunk_processor'
                }
            }
            llm_chunks.append(llm_chunk)
        
        return llm_chunks
    
    def _fallback_chunk_format(self, chunk: DocumentChunk) -> Dict[str, Any]:
        # Fallback format if optimization fails.
        return {
            'id': chunk.id,
            'original_title': chunk.subtopic_title,
            'clean_title': chunk.subtopic_title,
            'section_number': '',
            'page_number': chunk.page_number + 1,
            'content_type': 'text',
            # 'structured_content': chunk.text,  # REMOVED - too verbose
            'concepts': '',  # Empty string instead of array
            'code_examples_count': 0,
            'exercises_count': 0,
            'text_length': len(chunk.text),
            'llm_context': chunk.text[:500] + '...' if len(chunk.text) > 500 else chunk.text,  # Truncate for brevity
            'rag_keywords': [],
            'title_cleaned': False,
            'content_improved': False,
            'structure_enhanced': False,
        }
