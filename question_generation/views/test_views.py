from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from ..helpers.llm_utils import invoke_deepseek
from ..helpers.deepseek_prompts import deepseek_prompt_manager


@api_view(['POST'])
def deepseek_test_view(request):
    # test deepseek api connectivity and functionality.
    #
    # post {
    #     "prompt": "your prompt here",
    #     "system_prompt": "...",
    #     "model": "deepseek-chat",
    #     "temperature": 0.7 (optional)
    # }
    #
    # returns: { "result": "...DeepSeek reply..." }
    try:
        # extract parameters
        prompt = request.data.get("prompt")
        system_prompt = request.data.get("system_prompt", "You are a helpful assistant.")
        model = request.data.get("model", "deepseek-chat")
        temperature = request.data.get("temperature")  # optional temperature parameter
        
        # validation
        if not prompt:
            return Response({
                "error": "Prompt required."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # prepare kwargs
        kwargs = {}
        if temperature is not None:
            kwargs['temperature'] = temperature
            
        # call llm
        result = invoke_deepseek(
            prompt, 
            system_prompt=system_prompt, 
            model=model, 
            **kwargs
        )
        
        return Response({
            "status": "success",
            "result": result,
            "model": model,
            "temperature": temperature
        })
        
    except Exception as e:
        return Response({
            "status": "error",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def test_prompt_generation(request):
    # test prompt generation for different game types.
    #
    # get /api/questions/test-prompts/?game_type=coding&subtopic=Variables&difficulty=beginner
    try:
        # get parameters
        game_type = request.GET.get('game_type', 'non_coding')
        subtopic_name = request.GET.get('subtopic', 'Python Basics')
        difficulty = request.GET.get('difficulty', 'beginner')
        num_questions = int(request.GET.get('num_questions', 2))
        
        # create test context
        context = {
            'subtopic_name': subtopic_name,
            'difficulty': difficulty,
            'num_questions': num_questions,
            'rag_context': f"Test RAG context for {subtopic_name} at {difficulty} level."
        }
        
        # generate prompt
        prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
        
        return Response({
            'status': 'success',
            'game_type': game_type,
            'context': context,
            'generated_prompt': prompt
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Prompt generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    # simple health check endpoint.
    return Response({
        'status': 'healthy',
        'service': 'question_generation',
        'version': '2.0.0 (modular)',
        'timestamp': str(timezone.now())
    })


@api_view(['GET'])
def get_generation_stats(request):
    # get basic statistics about generated questions.
    try:
        from question_generation.models import GeneratedQuestion
        
        total_questions = GeneratedQuestion.objects.count()
        coding_questions = GeneratedQuestion.objects.filter(game_type='coding').count()
        non_coding_questions = GeneratedQuestion.objects.filter(game_type='non_coding').count()
        
        difficulty_stats = {}
        for difficulty in ['beginner', 'intermediate', 'advanced', 'master']:
            difficulty_stats[difficulty] = GeneratedQuestion.objects.filter(difficulty=difficulty).count()
        
        return Response({
            'status': 'success',
            'statistics': {
                'total_questions': total_questions,
                'by_game_type': {
                    'coding': coding_questions,
                    'non_coding': non_coding_questions
                },
                'by_difficulty': difficulty_stats
            }
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Failed to get statistics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
