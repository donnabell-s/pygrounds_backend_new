from .imports import *
from ..helpers.deepseek_prompts import deepseek_prompt_manager
from ..helpers.llm_utils import invoke_deepseek
from django.db import transaction
import json


@api_view(['POST'])
def deepseek_test_view(request):
    """
    POST { "prompt": "your prompt here", "system_prompt": "...", "model": "..." }
    Returns: { "result": "...DeepSeek reply..." }
    """
    prompt = request.data.get("prompt")
    system_prompt = request.data.get("system_prompt", "You are a helpful assistant.")
    model = request.data.get("model", "deepseek-chat")
    try:
        if not prompt:
            return Response({"error": "Prompt required."}, status=400)
        result = invoke_deepseek(prompt, system_prompt=system_prompt, model=model)
        return Response({"result": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
@api_view(['POST'])
def generate_questions_with_deepseek(request, subtopic_id=None):
    try:
        mode = request.data.get('mode', 'minigame')
        batch = bool(request.data.get('batch', True))
        total_num_questions = int(request.data.get('total_num_questions', 10))  # for pre_assessment
        num_questions_per = int(request.data.get('num_questions_per', 2))       # for minigame
        generated_questions = []
        difficulty_levels = ['beginner', 'intermediate', 'advanced', 'master']

        if mode == 'minigame':
            minigame_type = request.data.get('minigame_type')
            if not minigame_type:
                return Response({'status': 'error', 'message': 'minigame_type required'}, status=400)

            subtopic_ids = request.data.get('subtopic_ids')
            topic_ids = request.data.get('topic_ids')

            # Get subtopics based on provided ids or fallback to single subtopic_id
            if subtopic_ids:
                subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids))
            elif topic_ids:
                subtopics = list(Subtopic.objects.filter(topic_id__in=topic_ids))
            elif subtopic_id:
                subtopics = [get_object_or_404(Subtopic, id=subtopic_id)]
            else:
                return Response({'status': 'error', 'message': 'Provide subtopic_ids, topic_ids, or subtopic_id'}, status=400)

            rag_context = ""

            # Build loop_set: all difficulties except master first
            loop_set = []
            for s in subtopics:
                for d in difficulty_levels:
                    if d != 'master':
                        for i in range(num_questions_per):
                            loop_set.append((s, d, i))

            # Add exactly one master question for the first subtopic if available
            if subtopics:
                loop_set.insert(0, (subtopics[0], 'master', 0))

            # Generate questions from loop_set
            for subtopic, difficulty, idx in loop_set:
                context = {
                    'rag_context': rag_context,
                    'subtopic_name': subtopic.name,
                    'subtopic_description': '',  # No description field in Subtopic model
                    'difficulty': difficulty,
                    'learning_objectives': getattr(subtopic, 'learning_objectives', None),
                    'question_type': 'coding' if 'coding' in minigame_type else 'non_coding',
                    'cross_subtopic_mixing': False,
                    'related_subtopics': [],
                }
                prompt = deepseek_prompt_manager.get_prompt_for_minigame(minigame_type, context)
                try:
                    llm_response = invoke_deepseek(prompt, system_prompt="You are a helpful assistant.", model="deepseek-chat")
                except Exception as e:
                    llm_response = f"DeepSeek call failed: {e}"

                generated_questions.append({
                    'prompt': prompt,
                    'context': context,
                    'llm_response': llm_response,
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'topic_id': subtopic.topic.id,
                    'topic_name': subtopic.topic.name,
                    'difficulty': difficulty,
                    'metadata': {'missing': True}
                })

        elif mode == 'pre_assessment':
            topic_ids = request.data.get('topic_ids', None)
            topics = Topic.objects.filter(id__in=topic_ids) if topic_ids else Topic.objects.all()

            # Compose topics and their subtopics string for prompt
            topics_and_subtopics_parts = []
            all_available_subtopics = []  # For debugging
            for topic in topics:
                subtopics = list(topic.subtopics.values_list('name', flat=True))
                all_available_subtopics.extend(subtopics)

                # Debug print for verification
                print(f"Topic: {topic.name}")
                print(f"Subtopics: {subtopics}")

                section = f'Topic: "{topic.name}"\nSubtopics:\n' + "\n".join([f"- {s}" for s in subtopics])
                topics_and_subtopics_parts.append(section)

            topics_and_subtopics_str = "\n\n".join(topics_and_subtopics_parts)

            # Debug print full topics string
            print("Full topics_and_subtopics_str sent to prompt:")
            print(topics_and_subtopics_str)
            print(f"All available subtopics: {all_available_subtopics}")
            print("=" * 60)

            context = {
                'topics_and_subtopics': topics_and_subtopics_str,
                'num_questions': total_num_questions
            }

            system_prompt = (
    f"You are a Python assessment expert creating a concise pre-assessment for users. "
    f"Ensure that all listed topics and their subtopics are comprehensively covered within the total of {total_num_questions} questions. "
    f"To achieve this, generate many questions that cover multiple subtopics together, testing integrated understanding. "
    f"Cover various difficulty levels and always use the exact subtopic names from the provided list."
)


            prompt = deepseek_prompt_manager.get_prompt_for_minigame("pre_assessment", context)
            try:
                llm_response = invoke_deepseek(
                    prompt,
                    system_prompt=system_prompt,
                    model="deepseek-reasoner"
                )
            except Exception as e:
                llm_response = f"DeepSeek call failed: {e}"
                generated_questions.append({'error': llm_response})

            clean_resp = llm_response.strip()
            
            # Handle markdown code blocks
            if "```json" in clean_resp:
                # Extract JSON between ```json and ```
                start_idx = clean_resp.find("```json") + 7
                end_idx = clean_resp.find("```", start_idx)
                if end_idx != -1:
                    clean_resp = clean_resp[start_idx:end_idx].strip()
            elif clean_resp.startswith("```") and clean_resp.endswith("```"):
                # Simple code block without json marker
                clean_resp = clean_resp[3:-3].strip()
                if clean_resp.lower().startswith("json"):
                    clean_resp = clean_resp[4:].strip()

            try:
                questions_json = json.loads(clean_resp)
                
                # Validate that we got the expected number of questions
                actual_count = len(questions_json)
                if actual_count != total_num_questions:
                    print(f"❌ ERROR: Expected {total_num_questions} questions, but got {actual_count}")
                    
                    # If we got more questions than requested, truncate to the exact number
                    if actual_count > total_num_questions:
                        print(f"🔧 Truncating from {actual_count} to {total_num_questions} questions")
                        questions_json = questions_json[:total_num_questions]
                    # If we got fewer questions, return an error
                    else:
                        return Response({
                            'status': 'error',
                            'message': f"LLM generated only {actual_count} questions instead of {total_num_questions}. Please try again.",
                            'raw_response': llm_response
                        }, status=500)
                
                print(f"✅ Processing {len(questions_json)} questions (exactly as requested)")
                
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f"JSON parse error: {str(e)}",
                    'raw_response': llm_response
                }, status=500)
            
            PreAssessmentQuestion.objects.all().delete()  # Delete all existing pre-assessment questions
            print("Deleted all existing pre-assessment questions")

            # Pre-load all subtopics and topics for efficient matching (single DB query)
            all_subtopics = list(Subtopic.objects.select_related('topic').all())
            all_topics = list(topics)
            
            # Create lookup dictionaries for O(1) exact matching
            subtopic_exact_map = {s.name: s for s in all_subtopics}
            subtopic_lower_map = {s.name.lower(): s for s in all_subtopics}
            
            # Special case mappings for common LLM variations
            special_mappings = {
                'list comprehension': 'List Indexing, Slicing, and Comprehension',
                'dictionary comprehension': 'Dictionary Comprehensions', 
                'dict comprehension': 'Dictionary Comprehensions',
                'input': 'input() to read user data',
                'type conversion': 'Type Conversion and Casting',
                'type casting': 'Type Conversion and Casting',
                'casting': 'Type Conversion and Casting'
            }
            
            print("Processing questions and matching subtopics...")
            for idx, q in enumerate(questions_json):
                print(f"\nProcessing question {idx + 1}:")
                print(f"Question: {q.get('question', '')[:60]}...")
                
                subtopic_names = q.get("subtopics_covered", [])
                if isinstance(subtopic_names, str):
                    subtopic_names = [subtopic_names]
                
                print(f"LLM returned subtopics: {subtopic_names}")
                
                # Fast in-memory subtopic matching for multiple subtopics
                matched_subtopics = []
                matched_topics = []
                primary_subtopic_obj = None
                primary_topic_obj = None
                
                if subtopic_names:
                    for subtopic_name in subtopic_names:
                        subtopic_name_clean = subtopic_name.strip()
                        matched_subtopic = None
                        
                        # 1. Exact match (O(1) lookup)
                        if subtopic_name_clean in subtopic_exact_map:
                            matched_subtopic = subtopic_exact_map[subtopic_name_clean]
                            print(f"Found exact match: '{subtopic_name}' -> '{matched_subtopic.name}'")
                        
                        # 2. Case-insensitive exact match (O(1) lookup)
                        elif subtopic_name_clean.lower() in subtopic_lower_map:
                            matched_subtopic = subtopic_lower_map[subtopic_name_clean.lower()]
                            print(f"Found case-insensitive match: '{subtopic_name}' -> '{matched_subtopic.name}'")
                        
                        # 3. Special case mappings (O(1) lookup)
                        elif subtopic_name_clean.lower() in special_mappings:
                            mapped_name = special_mappings[subtopic_name_clean.lower()]
                            if mapped_name in subtopic_exact_map:
                                matched_subtopic = subtopic_exact_map[mapped_name]
                                print(f"Found special mapping: '{subtopic_name}' -> '{matched_subtopic.name}'")
                        
                        # 4. Fast contains check (only if no exact matches found)
                        else:
                            for s in all_subtopics:
                                s_name_lower = s.name.lower()
                                subtopic_lower = subtopic_name_clean.lower()
                                if subtopic_lower in s_name_lower or s_name_lower in subtopic_lower:
                                    matched_subtopic = s
                                    print(f"Found fuzzy match: '{subtopic_name}' -> '{matched_subtopic.name}'")
                                    break
                        
                        # Add to matched lists if found
                        if matched_subtopic:
                            if matched_subtopic not in matched_subtopics:  # Avoid duplicates
                                matched_subtopics.append(matched_subtopic)
                                if matched_subtopic.topic not in matched_topics:
                                    matched_topics.append(matched_subtopic.topic)
                            
                            # Set primary subtopic/topic (first match)
                            if not primary_subtopic_obj:
                                primary_subtopic_obj = matched_subtopic
                                primary_topic_obj = matched_subtopic.topic
                        else:
                            print(f"No match found for subtopic: '{subtopic_name}'")
                
                # Topic fallback matching (fast in-memory) if no subtopics matched
                if not primary_topic_obj:
                    topic_name = q.get("topic", "")
                    if topic_name:
                        topic_name_clean = topic_name.strip().lower()
                        for topic in all_topics:
                            if topic.name.lower() == topic_name_clean:
                                primary_topic_obj = topic
                                if topic not in matched_topics:
                                    matched_topics.append(topic)
                                print(f"Found topic match: '{topic_name}' -> '{primary_topic_obj.name}'")
                                break
                
                # Final fallback
                if not primary_topic_obj and all_topics:
                    primary_topic_obj = all_topics[0]
                    if primary_topic_obj not in matched_topics:
                        matched_topics.append(primary_topic_obj)
                    print(f"Using fallback topic: {primary_topic_obj.name}")

                # Prepare data for storage - collect IDs instead of names
                matched_subtopic_ids = [s.id for s in matched_subtopics]
                matched_topic_ids = [t.id for t in matched_topics]
                
                print(f"Final assignment:")
                print(f"  Primary Topic: '{primary_topic_obj.name if primary_topic_obj else None}'")
                print(f"  Primary Subtopic: '{primary_subtopic_obj.name if primary_subtopic_obj else None}'")
                print(f"  All Topic IDs Covered: {matched_topic_ids}")
                print(f"  All Subtopic IDs Covered: {matched_subtopic_ids}")

                q_text = q.get("question_text") or q.get("question") or ""

                # Handle choices - should be a list of strings from the prompt template
                answer_opts = q.get("choices", [])
                if isinstance(answer_opts, dict):
                    # Fallback for dictionary format (legacy support)
                    answer_opts = [answer_opts[k] for k in sorted(answer_opts.keys())]
                elif not isinstance(answer_opts, list):
                    # Fallback for other formats
                    answer_opts = q.get("options", [])

                # Handle correct answer - preserve escape sequences properly
                correct_answer = q.get("correct_answer", "")
                
                print(f"📝 Original correct_answer: {repr(correct_answer)}")
                print(f"📝 Available choices: {[repr(choice) for choice in answer_opts]}")
                
                # If the correct answer contains actual newlines or escape sequences, 
                # we need to find the matching choice that has the same content
                if correct_answer and answer_opts:
                    # Try to find exact match first
                    if correct_answer not in answer_opts:
                        print(f"⚠️  Exact match not found, trying escape sequence matching...")
                        # Look for a match considering escape sequence differences
                        for choice in answer_opts:
                            # Compare with escape sequences resolved
                            try:
                                choice_decoded = choice.encode().decode('unicode_escape')
                                answer_decoded = correct_answer.encode().decode('unicode_escape')
                                if choice_decoded == answer_decoded:
                                    correct_answer = choice
                                    print(f"🔧 Matched correct answer via escape sequence: {repr(correct_answer)}")
                                    break
                                # Also try the reverse - sometimes the JSON parsing affects one but not the other
                                elif choice == answer_decoded:
                                    correct_answer = choice
                                    print(f"🔧 Matched correct answer via reverse escape: {repr(correct_answer)}")
                                    break
                            except Exception as e:
                                print(f"⚠️  Error processing escape sequences: {e}")
                                continue
                        else:
                            print(f"❌ Warning: correct_answer {repr(correct_answer)} not found in choices {[repr(c) for c in answer_opts]}")
                            # Use the first choice as fallback
                            if answer_opts:
                                correct_answer = answer_opts[0]
                                print(f"🔧 Using first choice as fallback: {repr(correct_answer)}")
                    else:
                        print(f"✅ Exact match found for correct_answer: {repr(correct_answer)}")

                paq = PreAssessmentQuestion.objects.create(
                    topic_ids=matched_topic_ids,
                    subtopic_ids=matched_subtopic_ids,
                    question_text=q_text,
                    answer_options=answer_opts,
                    correct_answer=correct_answer,  # Use the processed correct_answer
                    estimated_difficulty=q.get("difficulty", "beginner"),
                    order=idx
                )

                # Get names for API response
                matched_subtopic_names = [s.name for s in matched_subtopics]
                matched_topic_names = [t.name for t in matched_topics]

                generated_questions.append({
                    'id': paq.id,
                    'topic_ids': matched_topic_ids,  # Return IDs
                    'subtopic_ids': matched_subtopic_ids,  # Return IDs
                    'topics_covered': matched_topic_names,  # Return names for readability
                    'subtopics_covered': matched_subtopic_names,  # Return names for readability
                    'question': paq.question_text,
                    'correct_answer': paq.correct_answer,
                    'choices': paq.answer_options,
                    'difficulty': paq.estimated_difficulty
                })

        else:
            return Response({'status': 'error', 'message': f'Unknown mode: {mode}'}, status=400)

        return Response({
            'status': 'success',
            'questions': generated_questions,
            'mode': mode,
            'total_generated': len(generated_questions)
        })

    except Exception as e:
        logger.error(f"DeepSeek question generation failed: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=500)
