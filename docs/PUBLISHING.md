# Maintaining the GitHub repository

The canonical repository is [Afloat16/recontrail](https://github.com/Afloat16/recontrail). The repository homepage reads the English `README.md`; `README.zh-CN.md` is the full Chinese version. `README.en.md` remains a compatibility link.

## Review before pushing

Use a branch for ongoing maintenance. Review the diff, run the tests, and avoid adding user photographs, output geometry, credentials, or virtual environments.

```bash
git clone https://github.com/Afloat16/recontrail.git
cd recontrail
git switch -c docs/update-guide
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
git diff --check
git status --short
```

Stage intended files explicitly. Commit and push the branch, then open a pull request. Do not use force pushes to replace shared history.

## Repository description and topics

Copy-ready English introductions, a launch post, and grouped search phrases are in [PROJECT_COPY.md](PROJECT_COPY.md). The recommended description and 20 topics are stored in [`.github/repository-metadata.json`](../.github/repository-metadata.json). This file does not change GitHub settings automatically.

On GitHub, open the repository's **About** gear, paste the description and topics, and save. Alternatively, after authenticating your own GitHub CLI, use the checked-in values:

```bash
gh repo edit Afloat16/recontrail --description "Local-first 3D reconstruction on your CPU. Inspect photo quality, recover sparse geometry and camera poses, reconstruct calibrated stereo, and share offline interactive reports. No cloud, GPU, or model downloads required."
gh api --method PUT repos/Afloat16/recontrail/topics --input .github/repository-topics.json
```

The first command changes the description. The second **replaces all topics** with the reviewed topic set; inspect existing settings before running it on a maintained repository. Do not paste credentials into files or issues. GitHub documents [topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics) and [repository editing](https://cli.github.com/manual/gh_repo_edit).

## Publication evidence

A source package or prepared commit is not proof of a completed upload. Confirm the remote branch, inspect the files at the resulting commit, and read the actual Actions result. Keep historical validation records distinct from current remote state. A tag or GitHub Release is a separate action from uploading source; do not describe one as published until it exists.

## Legacy new-repository helper

`scripts/publish.py` is a conservative helper for first publication to a **new**, absent personal repository from a directory without `.git`. It deliberately refuses an existing repository or checkout. Do not use it to update `Afloat16/recontrail` now that this repository exists.

Its `--dry-run` mode remains useful for checking the source allowlist and obvious secret patterns without Git or network writes. It is not a comprehensive security scanner.

```bash
python scripts/publish.py --dry-run
```
