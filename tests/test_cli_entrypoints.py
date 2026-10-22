"""CLI routing and dependency boundaries, independent of historical judgments."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_core_verification_does_not_load_display_dependencies():
    code = '''
import contextlib, io, json, sys
from emperor_v4.eval import main
class NoDisplay:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'matplotlib', 'PIL', 'numpy'}:
            raise AssertionError('core command loaded display dependency: ' + fullname)
sys.meta_path.insert(0, NoDisplay())
with contextlib.redirect_stdout(io.StringIO()):
    assert main(['project-entries-verify']) == 0
assert 'emperor_v4.evaluation.profile_video_card' not in sys.modules
assert 'emperor_v4.evaluation.first_item_a_registry' not in sys.modules
print(json.dumps({'status': 'PASS'}))
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"
