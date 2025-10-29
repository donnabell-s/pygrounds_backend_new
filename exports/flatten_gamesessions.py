import sys
import json
import csv


def flatten(input_json_path, output_csv_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fieldnames = [
        'session_pk', 'session_id', 'user_id', 'username', 'session_game_type', 'session_status',
        'start_time', 'end_time', 'total_score', 'time_limit',
        'gamequestion_id', 'generated_question_id', 'question_text', 'correct_answer', 'estimated_difficulty', 'question_game_type',
        'response_id', 'response_user_id', 'response_username', 'user_answer', 'is_correct', 'time_taken', 'answered_at'
    ]

    rows = []
    for s in data:
        base = {
            'session_pk': s.get('id'),
            'session_id': s.get('session_id'),
            'user_id': s.get('user_id'),
            'username': s.get('username'),
            'session_game_type': s.get('game_type'),
            'session_status': s.get('status'),
            'start_time': s.get('start_time'),
            'end_time': s.get('end_time'),
            'total_score': s.get('total_score'),
            'time_limit': s.get('time_limit'),
        }

        for gq in s.get('game_questions', []):
            gen = gq.get('generated_question', {})
            if gq.get('responses'):
                for resp in gq.get('responses'):
                    row = base.copy()
                    row.update({
                        'gamequestion_id': gq.get('gamequestion_id'),
                        'generated_question_id': gen.get('generated_question_id'),
                        'question_text': gen.get('question_text'),
                        'correct_answer': gen.get('correct_answer'),
                        'estimated_difficulty': gen.get('estimated_difficulty'),
                        'question_game_type': gen.get('game_type'),
                        'response_id': resp.get('response_id'),
                        'response_user_id': resp.get('user_id'),
                        'response_username': resp.get('username'),
                        'user_answer': resp.get('user_answer'),
                        'is_correct': resp.get('is_correct'),
                        'time_taken': resp.get('time_taken'),
                        'answered_at': resp.get('answered_at'),
                    })
                    rows.append(row)
            else:
                row = base.copy()
                row.update({
                    'gamequestion_id': gq.get('gamequestion_id'),
                    'generated_question_id': gen.get('generated_question_id'),
                    'question_text': gen.get('question_text'),
                    'correct_answer': gen.get('correct_answer'),
                    'estimated_difficulty': gen.get('estimated_difficulty'),
                    'question_game_type': gen.get('game_type'),
                    'response_id': None,
                    'response_user_id': None,
                    'response_username': None,
                    'user_answer': None,
                    'is_correct': None,
                    'time_taken': None,
                    'answered_at': None,
                })
                rows.append(row)

    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python flatten_gamesessions.py input.json output.csv')
        sys.exit(1)
    flatten(sys.argv[1], sys.argv[2])
