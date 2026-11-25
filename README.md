# My MLOps Project

Your semester-long project for **Lifecycle of Artificial Intelligence Systems**.
You start from this minimal, working baseline and grow it into a full MLOps
project across HW1–HW5 — see [`HOMEWORK.md`](HOMEWORK.md).

This repo is **separate from the course materials**. The course repo (lectures,
labs, datasets, homework briefs) you read and do the labs in; *this* repo is your
own project, on your own dataset, and is what gets graded.

## What's here

```
src/mlops_project/   config.py · data.py · model.py · cli.py   (a simple baseline pipeline)
src/main.py          entry point
tests/               smoke tests that pass on synthetic data (no dataset needed)
data/                put your dataset here (see data/README.md)
docs/                DATA_DICTIONARY.md (fill it in) + your proposal
.env.example         configuration — copy to .env
```

The baseline trains a scikit-learn `StandardScaler` + (logistic or linear)
regression on a CSV you point it at — classification or regression, set by
`PROBLEM_TYPE`. It's deliberately simple; the course is about the lifecycle, not
the model.

## Quick start

Prerequisites are `uv` (https://docs.astral.sh/uv/), Python 3.12 or newer (uv installs it) and Docker for the local services.

```bash
uv sync --locked --all-groups   # install the exact locked environment
cp .env.example .env            # configuration, the values are placeholders
uv run pytest -q                # tests pass with Docker stopped
make up                         # Postgres, Silo and MLflow, waits for the healthchecks
make dvc-pull                   # fetch the tracked data from Silo
make repro                      # validate, prepare, train, evaluate and gate
```

## Next

1. Add your dataset to `data/` and document it in `docs/DATA_DICTIONARY.md`.
2. Write your one-page proposal in `docs/proposal.md` (Week 2 milestone).
3. Follow [`HOMEWORK.md`](HOMEWORK.md) from HW1 onward.
