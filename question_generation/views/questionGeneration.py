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
    """
    Generate questions via DeepSeek LLM for minigame or pre-assessment.
    Flexible: supports per-request (single/batch) and full topic/subtopic coverage.
    """
    try:
        mode = request.data.get('mode', 'minigame')
        batch = bool(request.data.get('batch', True))
        num_questions_per = int(request.data.get('num_questions_per', 1))
        generated_questions = []
        difficulty_levels = ['beginner', 'intermediate', 'advanced', 'expert', 'hard']

        # --- MINIGAME MODE ---
        if mode == 'minigame':
            minigame_type = request.data.get('minigame_type')
            if not minigame_type:
                return Response({'status': 'error', 'message': 'minigame_type required'}, status=400)
            subtopic_ids = request.data.get('subtopic_ids')
            topic_ids = request.data.get('topic_ids')
            subtopics = []
            if subtopic_ids:
                subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids))
            elif topic_ids:
                subtopics = list(Subtopic.objects.filter(topic_id__in=topic_ids))
            elif subtopic_id:
                subtopics = [get_object_or_404(Subtopic, id=subtopic_id)]
            else:
                return Response({'status': 'error', 'message': 'Provide subtopic_ids, topic_ids, or subtopic_id'}, status=400)

            rag_context = ""
            loop_set = (
                [(s, d, i)
                 for s in subtopics
                 for d in difficulty_levels
                 for i in range(num_questions_per)]
                if batch else
                [(subtopics[0], request.data.get('difficulty', 'beginner'), 0)]
            )
            for subtopic, difficulty, idx in loop_set:
                context = {
                    'rag_context': rag_context,
                    'subtopic_name': subtopic.name,
                    'subtopic_description': getattr(subtopic, 'description', ''),
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
                question = {
                    'prompt': prompt,
                    'context': context,
                    'llm_response': llm_response,
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'topic_id': subtopic.topic.id,
                    'topic_name': subtopic.topic.name,
                    'difficulty': difficulty,
                    'metadata': {'missing': True}
                }
                generated_questions.append(question)

       
        # --- PRE-ASSESSMENT MODE ---
            # --- PRE-ASSESSMENT MODE ---
        elif mode == 'pre_assessment':
            topic_ids = request.data.get('topic_ids', None)
            if not topic_ids:
                topics = Topic.objects.all()
            else:
                topics = Topic.objects.filter(id__in=topic_ids)

            # Build topics and subtopics string for all topics at once
            topics_and_subtopics_parts = []
            for topic in topics:
                subtopics = list(topic.subtopics.values_list('name', flat=True))
                topic_section = f'Topic: "{topic.name}"\nSubtopics:\n' + \
                    "\n".join([f"- {s}" for s in subtopics])
                topics_and_subtopics_parts.append(topic_section)
            
            topics_and_subtopics_str = "\n\n".join(topics_and_subtopics_parts)
            
            # Generate questions for all topics at once
            context = {
                'topics_and_subtopics': topics_and_subtopics_str,
                'num_questions': num_questions_per * len(topics)
            }
            
            prompt = deepseek_prompt_manager.get_prompt_for_minigame("pre_assessment", context)
            try:
                llm_response = invoke_deepseek(
                    prompt,
                    system_prompt="You are a Python assessment expert creating a concise pre-assessment for users, with at most 20 questions total.",
                    model="deepseek-reasoner"
                )
            except Exception as e:
                llm_response = f"DeepSeek call failed: {e}"
                generated_questions.append({'error': llm_response})
                # You may want to return here or continue depending on your error handling

            # Clean up LLM response (strip markdown code blocks if present)
            clean_resp = llm_response.strip()
            if clean_resp.startswith("```"):
                clean_resp = clean_resp.strip("`")
                if clean_resp.lower().startswith("json"):
                    clean_resp = clean_resp[4:].strip()

            try:
                questions_json = json.loads(clean_resp)
            except Exception as e:
                generated_questions.append({'error': f"JSON parse error: {str(e)}", 'raw': llm_response})
                # Return early or continue, depending on your app logic
                return Response({
                    'status': 'error',
                    'message': f"JSON parse error: {str(e)}",
                    'raw_response': llm_response
                }, status=500)

            # Save questions to DB and prepare response list
            for idx, q in enumerate(questions_json):
                subtopic_obj = None
                subtopic_names = q.get("subtopics_covered", [])
                if isinstance(subtopic_names, str):
                    subtopic_names = [subtopic_names]
                
                subtopics_qs = Subtopic.objects.filter(name__in=subtopic_names)
                if subtopics_qs.exists():
                    subtopic_obj = subtopics_qs.first()

                q_text = q.get("question_text") or q.get("question") or ""

                answer_opts = (
                    [q["choices"][k] for k in sorted(q["choices"].keys())]
                    if isinstance(q.get("choices"), dict) else q.get("options", [])
                )

                paq = PreAssessmentQuestion.objects.create(
                    topic=topics.first(),
                    subtopic=subtopic_obj,
                    question_text=q_text,
                    answer_options=answer_opts,
                    correct_answer=q.get("correct_answer", ""),
                    explanation=q.get("explanation", ""),
                    estimated_difficulty=q.get("difficulty", "beginner"),
                    order=idx
                )

                generated_questions.append({
                    'id': paq.id,
                    'topic': paq.topic.name,
                    'question': paq.question_text,
                    'correct_answer': paq.correct_answer,
                    'choices': paq.answer_options,
                    'difficulty': paq.estimated_difficulty
                })

        return Response({
            'status': 'success', 
            'questions': generated_questions,
            'mode': mode,
            'total_generated': len(generated_questions)
        })

    except Exception as e:
        logger.error(f"DeepSeek question generation failed: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=500)

