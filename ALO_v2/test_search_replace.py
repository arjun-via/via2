"""Test the new SEARCH/REPLACE approach"""
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env manually
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

from ALO_v2 import ALOv2Orchestrator

print('Testing new SEARCH/REPLACE approach...')
print('='*60)

orch = ALOv2Orchestrator()

result = orch.solve(
    instance_id='django__django-11292',
    problem_statement='QuerySet.union() with values_list() returns columns in wrong order. The extra_select dict unpacks keys instead of values.',
    test_cmd='python tests/runtests.py queries.test_qs_combinators --settings=test_sqlite -v2'
)

print()
print('='*60)
print(f'Success: {result["success"]}')
print(f'Tests passed: {result["tests_passed"]}')
print(f'Attempts: {result["attempts"]}')
print(f'Cost: ${result["total_cost"]:.4f}')

if result['patch']:
    print()
    print('PATCH:')
    print(result['patch'][:500])
