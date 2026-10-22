"""CLI routing and dependency boundaries, independent of historical judgments."""
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from emperor_v4 import eval as cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("command,script", [("reader", "reader/build_site.py"), ("package", "package_net_review.py")])
def test_workspace_commands_forward_arguments_to_existing_implementation(monkeypatch, command, script):
    calls = []
    def load(path):
        assert Path(path) == ROOT / script
        return {"main": lambda argv: calls.append(argv)}
    monkeypatch.setattr(runpy, "run_path", load)
    assert cli.main([command, "--help"]) == 0
    assert calls == [["--help"]]


def test_workspace_command_failure_is_not_reported_as_success(monkeypatch):
    def fail(argv):
        raise ValueError("build failed")
    monkeypatch.setattr(runpy, "run_path", lambda path: {"main": fail})
    with pytest.raises(ValueError, match="build failed"):
        cli.main(["reader"])


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
