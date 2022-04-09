"""
Requires `python-decouple` package for accessing envvars.
"""
from __future__ import print_function

import re
from collections import OrderedDict
from sys import argv

import requests
from decouple import config


PROJECT_ID = '147'  # ETS/ticketing repo.
PROJECT_URL = '{}/api/v4/projects/{}/'.format(config('GITLAB_BASE_URL'), PROJECT_ID)
HEADERS = {'PRIVATE-TOKEN': config('GITLAB_PRIVATE_TOKEN')}


_components = []

non_backoffice_sites = [
    'acapi',
    'frontend',
    'processing',
    'redemption',
    'scapi',
    'taapi',
    'worker',
]
for site in non_backoffice_sites:
    _components.append('test:{}:common'.format(site))
    _components.append('test:{}:core'.format(site))

backoffice_components = [
    'test:backoffice:common: [0]',
    'test:backoffice:common: [1]',
    'test:backoffice:core: [0]',
    'test:backoffice:core: [1]',
    'test:backoffice:core: [2]',
    'test:backoffice:core: [3]',
    'test:backoffice:core: [4]',
    'test:backoffice:core: [5]',
    'test:backoffice:core: [6]',
    'test:backoffice:core: [7]',
]
_components.extend(backoffice_components)


SUCCESS = 'SUCCESS'

# Sequencing is important for consistency with CI ordering.
COMPONENTS = OrderedDict()
for _component in _components:
    # Assume all test jobs are successful by default,
    # and override only in case of failures.
    COMPONENTS[_component] = SUCCESS


def get_job_stats_line(job_id):
    JOB_LOG_API = 'jobs/{}/trace'.format(job_id)
    r = requests.get(
        '{}{}'.format(PROJECT_URL, JOB_LOG_API),
        headers=HEADERS,
    )

    lines = r.text.splitlines()
    for line in lines:
        summary_line_indicator = 'skipped='
        if summary_line_indicator in line:
            return line
    return 'ERROR!!!'


def get_stats_details(job_stats):
    match = re.search('errors=(\d+)', job_stats)
    errors = 0
    if match:
        errors = int(match.group(1))

    match = re.search('failures=(\d+)', job_stats)
    failures = 0
    if match:
        failures = int(match.group(1))

    return (errors, failures)


def get_pipeline_stats(pipeline_id):
    pagination = 50

    # Get the failed jobs only.
    PIPELINE_JOBS_API = 'pipelines/{}/jobs?per_page={}&scope[]=failed'.format(
        pipeline_id,
        pagination,
    )
    r = requests.get(
        '{}{}'.format(PROJECT_URL, PIPELINE_JOBS_API),
        headers=HEADERS,
    )

    errors = 0
    failures = 0
    jobs = r.json()
    for job in jobs:
        job_id = job['id']
        job_name = job['name']

        # Get the unit "test" jobs only.
        if job_name.startswith('test'):
            job_stats = get_job_stats_line(job_id)

            if 'FAILED' in job_stats:
                _errors, _failures = get_stats_details(job_stats)

                errors += _errors
                failures += _failures

                # Reformat the FAILED stats for better UX.
                job_stats = 'FAILED:   {:10}  {:14}'.format(
                    'errors={}'.format(_errors),
                    'failures={}'.format(_failures),
                )

            COMPONENTS[job_name] = job_stats

    return (errors, failures)


pipeline_id = argv[1]
errors, failures = get_pipeline_stats(pipeline_id)
for component, value in COMPONENTS.items():
    output = '{:30} {}'.format(component, value)
    print(output)


# Summary
print('=' * 70)
print()
print('TOTAL')
print('{:30} {}'.format('Errors', errors))
print('{:30} {}'.format('Failures', failures))
