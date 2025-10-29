from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from minigames.models import GameSession, GameQuestion, QuestionResponse, WordSearchData, HangmanData, CrosswordData
from question_generation.models import GeneratedQuestion
import json


def serialize_datetime(value):
    try:
        return value.isoformat()
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Export GameSession(s) and related GameQuestion data to JSON. By default exports ids 224-235.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=int, help='Start GameSession id (inclusive)', default=224)
        parser.add_argument('--end', type=int, help='End GameSession id (inclusive)', default=235)
        parser.add_argument('--ids', type=str, help='Comma-separated list of GameSession ids to export', default=None)
        parser.add_argument('--output', type=str, help='Output file path', default='exports/gamesessions_224_235.json')

    def handle(self, *args, **options):
        ids_arg = options.get('ids')
        start = options.get('start')
        end = options.get('end')
        output = options.get('output')

        if ids_arg:
            try:
                ids = [int(x.strip()) for x in ids_arg.split(',') if x.strip()]
            except ValueError:
                raise ValueError('Invalid --ids list; must be comma-separated integers')
            qs = GameSession.objects.filter(id__in=ids).order_by('id')
        else:
            qs = GameSession.objects.filter(id__gte=start, id__lte=end).order_by('id')

        result = []
        for session in qs.select_related('user'):
            sdict = {
                'id': session.id,
                'session_id': session.session_id,
                'user_id': session.user.id if session.user_id else None,
                'username': getattr(session.user, 'username', None),
                'game_type': session.game_type,
                'status': session.status,
                'start_time': serialize_datetime(session.start_time),
                'end_time': serialize_datetime(session.end_time),
                'total_score': session.total_score,
                'time_limit': session.time_limit,
            }

            # Include any OneToOne game-specific data if present
            try:
                ws = session.wordsearch_data
                sdict['wordsearch_data'] = {
                    'matrix': ws.matrix,
                    'placements': ws.placements,
                }
            except WordSearchData.DoesNotExist:
                pass

            try:
                hg = session.hangman_data
                sdict['hangman_data'] = {
                    'prompt': hg.prompt,
                    'function_name': hg.function_name,
                    'sample_input': hg.sample_input,
                    'sample_output': hg.sample_output,
                    'hidden_tests': hg.hidden_tests,
                }
            except HangmanData.DoesNotExist:
                pass

            try:
                cw = session.crossword_data
                sdict['crossword_data'] = {
                    'grid': cw.grid,
                    'placements': cw.placements,
                }
            except CrosswordData.DoesNotExist:
                pass

            # GameQuestion entries and linked GeneratedQuestion details
            gq_list = []
            for gq in session.session_questions.select_related('question').all():
                gen = gq.question
                gen_dict = {
                    'generated_question_id': gen.id,
                    'question_text': gen.question_text,
                    'correct_answer': gen.correct_answer,
                    'estimated_difficulty': gen.estimated_difficulty,
                    'game_type': gen.game_type,
                    'game_data': gen.game_data,
                }

                # Include responses for this GameQuestion
                responses = []
                for resp in gq.responses.select_related('user').all():
                    responses.append({
                        'response_id': resp.id,
                        'user_id': resp.user.id if resp.user_id else None,
                        'username': getattr(resp.user, 'username', None),
                        'user_answer': resp.user_answer,
                        'is_correct': resp.is_correct,
                        'time_taken': resp.time_taken,
                        'answered_at': serialize_datetime(resp.answered_at),
                    })

                gq_list.append({
                    'gamequestion_id': gq.id,
                    'generated_question': gen_dict,
                    'responses': responses,
                })

            sdict['game_questions'] = gq_list

            result.append(sdict)

        # Write out JSON
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, cls=DjangoJSONEncoder)

        self.stdout.write(self.style.SUCCESS(f'Exported {len(result)} GameSession(s) to {output}'))
