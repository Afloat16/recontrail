"""Pure preflight tests: never create a remote repository or use credentials."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('recontrail_publish', Path(__file__).parents[1] / 'scripts/publish.py')
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


def source_tree(tmp_path):
    for name in ('README.md', 'LICENSE', 'pyproject.toml', 'src/recontrail/__init__.py'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('test\n', encoding='utf-8')
    return tmp_path


def test_publication_allowlist_excludes_captures(tmp_path):
    root = source_tree(tmp_path)
    (root / 'capture').mkdir()
    (root / 'capture/private.png').write_bytes(b'private capture')
    (root / '.env').write_text('PRIVATE=yes')
    files = publish.source_files(root)
    assert len(files) == 4
    assert not any('capture' in path or path == '.env' for path in files)


def test_publication_stops_on_possible_secret(tmp_path):
    root = source_tree(tmp_path)
    # Construct a non-working synthetic test value, not a real credential.
    (root / 'README.md').write_text('ghp_' + 'x' * 36)
    with pytest.raises(ValueError, match='credential'):
        publish.source_files(root)


def test_publication_stops_on_symlinks(tmp_path):
    root = source_tree(tmp_path)
    try:
        (root / 'src/shared.py').symlink_to(root / 'README.md')
    except (OSError, NotImplementedError):
        pytest.skip('Local platform does not permit creating a symlink')
    with pytest.raises(ValueError, match='Symlinks'):
        publish.source_files(root)


def test_dry_run_never_invokes_git_or_network(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError('Dry run must not invoke Git or GitHub CLI')
    monkeypatch.setattr(publish, 'invoke', prohibited)
    assert publish.main(['--dry-run']) == 0


def test_publication_requires_explicit_consent(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError('Publication without confirmation attempted external access')
    monkeypatch.setattr(publish, 'invoke', prohibited)
    assert publish.main([]) == 2
