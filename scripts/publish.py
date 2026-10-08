"""First publication of a reviewed source checkout to a NEW personal public repo.

No credentials are read or stored by this script. Authentication is delegated to
GitHub CLI. Existing Git repositories/remotes are deliberately not modified.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT_FILES = {
    '.gitignore', '.gitattributes', 'pyproject.toml', 'MANIFEST.in', 'LICENSE',
    'README.md', 'README.zh-CN.md', 'README.en.md', 'THIRD_PARTY_NOTICES.md', 'CITATION.cff',
    'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md', 'start.sh', 'start.bat',
}
SOURCE_DIRS = {'src', 'tests', 'docs', 'examples', 'scripts', '.github'}
SUFFIXES = {'.py', '.md', '.toml', '.yml', '.yaml', '.cff', '.bib', '.json',
            '.css', '.js', '.html', '.png', '.sh', '.bat', '.txt'}
IGNORE_PARTS = {'__pycache__', '.pytest_cache', '.ruff_cache', '.venv', 'node_modules'}
SECRET_PATTERNS = (
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
    re.compile(rb'AKIA[A-Z0-9]{16}'),
)


def source_files(root: Path) -> list[str]:
    """Explicit source allowlist; never add captures, virtualenvs or all of '.'."""
    files: list[str] = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if rel.parts[0] not in SOURCE_DIRS and rel.as_posix() not in ROOT_FILES:
            continue
        if any(p in IGNORE_PARTS or p.endswith('.egg-info') for p in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlinks are not published: {rel}')
        if not path.is_file():
            continue
        if rel.as_posix() not in ROOT_FILES and path.suffix.lower() not in SUFFIXES:
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError(f'Review this unexpectedly large source asset: {rel}')
        content = path.read_bytes()
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise ValueError(f'Possible credential in {rel}; publication stopped.')
        files.append(rel.as_posix())
    for required in ('README.md', 'LICENSE', 'pyproject.toml', 'src/recontrail/__init__.py'):
        if required not in files:
            raise ValueError(f'Not a complete ReconTrail source directory: missing {required}')
    return files


def invoke(root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=root, text=True, capture_output=True,
                            encoding='utf-8', errors='replace', timeout=180,
                            env={**os.environ, 'GH_HOST': 'github.com', 'GH_PROMPT_DISABLED': '1'})
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} {args[1]} failed: {result.stderr.strip()[:1200]}')
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', default='Afloat16', help='Must match the authenticated personal account')
    parser.add_argument('--name', default='recontrail')
    parser.add_argument('--public', action='store_true', help='Explicitly select a public repository')
    parser.add_argument('--yes', action='store_true', help='Confirm publishing all allowlisted source files')
    parser.add_argument('--dry-run', action='store_true', help='List files only; no network or Git writes')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', args.owner):
            raise ValueError('Invalid personal GitHub login.')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', args.name):
            raise ValueError('Invalid repository name.')
        files = source_files(root)
        target = f'{args.owner}/{args.name}'
        print(f'New public repository: {target}\nReviewed source files: {len(files)}')
        for path in files:
            print(f'  {path}')
        if args.dry_run:
            print('Dry run only: no repository created, no files uploaded.')
            return 0
        if not (args.public and args.yes):
            raise ValueError('Review --dry-run, then explicitly pass --public --yes to publish.')
        if (root / '.git').exists():
            raise ValueError('A .git directory/file already exists. Refusing to modify an existing checkout. '
                             'See docs/PUBLISHING.md for manual continuation after a partial publication.')
        if not all(shutil.which(executable) for executable in ('git', 'gh')):
            raise ValueError('Install Git and GitHub CLI, then run gh auth login first.')
        invoke(root, ['gh', 'auth', 'status', '--hostname', 'github.com'])
        login = invoke(root, ['gh', 'api', 'user', '--jq', '.login']).stdout.strip()
        if login.casefold() != args.owner.casefold():
            raise ValueError(f'Authenticated as {login}, not {args.owner}; nothing published.')
        for field in ('user.name', 'user.email'):
            if not invoke(root, ['git', 'config', '--get', field], check=False).stdout.strip():
                raise ValueError(f'Set your Git {field} explicitly before creating the initial commit.')
        existing = invoke(root, ['gh', 'api', f'repos/{target}'], check=False)
        if existing.returncode == 0:
            raise ValueError(f'{target} already exists; refusing to push or overwrite it.')
        if 'HTTP 404' not in existing.stderr:
            raise RuntimeError('Cannot confirm that the remote is absent. Resolve network/authentication errors first.')
        invoke(root, ['git', 'init', '-b', 'main'])
        # Paths are explicit and use '--'; no shell, force push, wildcard or credential flags.
        for start in range(0, len(files), 50):
            invoke(root, ['git', 'add', '--', *files[start:start + 50]])
        staged = invoke(root, ['git', 'diff', '--cached', '--name-only', '-z']).stdout.split('\0')
        if set(filter(None, staged)) != set(files):
            raise RuntimeError('Staged files do not match the reviewed source allowlist; inspect Git status.')
        invoke(root, ['git', 'commit', '-m', 'Initial release: local reconstruction and capture diagnostics'])
        invoke(root, ['gh', 'repo', 'create', target, '--public', '--source', str(root),
                      '--remote', 'origin', '--push', '--description',
                      'Local-first photo diagnostics, sparse reconstruction and calibrated stereo'])
        remote = json.loads(invoke(root, ['gh', 'api', f'repos/{target}']).stdout)
        local_sha = invoke(root, ['git', 'rev-parse', 'HEAD']).stdout.strip()
        remote_sha = invoke(root, ['gh', 'api', f'repos/{target}/git/ref/heads/main',
                                   '--jq', '.object.sha']).stdout.strip()
        if remote.get('private') is not False or remote_sha != local_sha:
            raise RuntimeError('Publication verification failed. Check visibility and main branch on GitHub.')
        receipt = {'repository': target, 'url': remote['html_url'], 'visibility': 'public',
                   'commit': local_sha, 'verified': True}
        (root / 'publication-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(receipt, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'Publication stopped: {exc}\nIf a Git checkout or remote was created before this error, '
              'inspect it; no rollback, deletion or force push is performed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
