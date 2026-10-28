from pathlib import Path
import shutil
import subprocess
import pytest
import markdown2scorm

SCENARIOS = ['normal', 'standalone', 'preview', 'parent', 'opener', 'crossorigin', 'initfail',
             'completed', 'passed', 'failed', 'review', 'browse', 'brokenimage', 'throwget',
             'geterror', 'commitfail', 'reentrant', 'ready', 'hidden', 'bfcache']


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_runtime_with_mock_api(scenario):
    node = shutil.which('node')
    if not node:
        pytest.fail('Node.js requerido para comprobar el runtime SCORM (instale nodejs)')
    runtime = Path(markdown2scorm.__file__).parent / 'runtime/scorm12.js'
    result = subprocess.run([node, str(Path(__file__).with_name('runtime_harness.cjs')), scenario, str(runtime)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
