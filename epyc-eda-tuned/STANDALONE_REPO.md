# STANDALONE_REPO — extract `epyc-eda-tuned` as its own GitHub repository

This folder is designed to be **copy-paste extractable**.

## Option 1 — fresh repo from subdirectory (recommended)

```bash
# from monorepo root
git subtree split -P epyc-eda-tuned -b epyc-eda-tuned-split

mkdir -p ~/src/epyc-eda-tuned && cd ~/src/epyc-eda-tuned
git init
git pull /path/to/Physical-Design-Algorithms-Implementation epyc-eda-tuned-split

# create empty GitHub repo, then:
git remote add origin git@github.com:<you>/epyc-eda-tuned.git
git push -u origin main
```

Or simpler without subtree history:

```bash
cp -a epyc-eda-tuned ~/src/epyc-eda-tuned
cd ~/src/epyc-eda-tuned
git init
git add .
git commit -m "Initial import: epyc-eda TuneD lab"
gh repo create epyc-eda-tuned --public --source=. --remote=origin --push
```

## Option 2 — keep inside monorepo

No change required; treat `epyc-eda-tuned/` as the project root for docs/CI.

## Suggested GitHub metadata

- **Name:** `epyc-eda-tuned`
- **Description:** Rigorous lab for AMD TuneD profile epyc-eda — mirrored configs, BIOS checklist, CLAIM_GATE microbench
- **Topics:** `eda`, `epyc`, `tuned`, `linux-performance`, `physical-design`

## CI suggestion (optional)

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make bin test dry-inventory
```

Expect `claim_gate` to **SKIP** on GitHub-hosted runners (no writable sched knobs) — assert exit code 3, do not require PASS.
