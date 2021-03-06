import subprocess


def run_flow(text, job_id, count):
    # python -m luigi --module summarize RunFlow --term trump
    subprocess.run([
        'python',
        '-m',
        'luigi',
        '--module',
        'summarize',
        'RunFlow',
        '--term',
        text,
        '--jobid',
        str(job_id),
        '--count',
        str(count)
        ])
