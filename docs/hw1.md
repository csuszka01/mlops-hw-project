# HW 1 evidence

Project repository `https://github.com/csuszka01/mlops-hw-project`. The task is regression on the Emergency Dispatch and Traffic Physics data, the target is `Actual_Response_Time_min`. Columns are described in `docs/DATA_DICTIONARY.md`.

## R3 DVC tracking the dataset

The raw batches in `data/raw/` are committed to Git. The built file `data/measurements.csv` is tracked by DVC, and only its pointer is committed.

`data/measurements.csv.dvc` for dataset version 2 (current)

```
outs:
- md5: aed18119c18a85d1baae62dc4213b6a2
  size: 516869
  hash: md5
  path: measurements.csv
```

| Item | Value |
|---|---|
| md5 | `aed18119c18a85d1baae62dc4213b6a2` |
| size | 516869 bytes |
| rows | 8209 |
| columns | 11, ten features and the target |

`data/.gitignore`, written by DVC, holds `/measurements.csv`, so the data file is not in Git.

`.dvc/config` is committed

```
[core]
    autostage = true
    analytics = false
    check_update = false
    remote = storage
['remote "storage"']
    url = s3://dvc-storage/dvcstore
    endpointurl = http://127.0.0.1:5510
```

## R4 Silo as the DVC remote, both ways

The remote is the `dvc-storage` bucket in Silo, reached over `endpointurl`. `dvc push` stores the object under `files/md5/ae/d18119c18a85d1baae62dc4213b6a2`.

TODO add a screenshot of that object in the Silo console at http://127.0.0.1:5511.

`.dvc/config` holds no credentials. DVC reads the Silo keys from `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, which the Makefile maps from the `S3_*` values in `.env` for every dvc call. `.dvc/config.local` is not used, and DVC git-ignores it.

`dvc status --cloud` after both dataset versions were pushed

```
Cache and remote 'storage' are in sync.
```

Fresh clone proof, run in `/tmp` against the pushed repository

```
cd /tmp
git clone https://github.com/csuszka01/mlops-hw-project.git fresh-clone
cd fresh-clone
cp .env.example .env
ls data
```

`ls data` lists `processed`, `quality`, `raw`, `.gitignore`, `.gitkeep`, `dataset.csv`, `measurements.csv.dvc` and `README.md`, so `measurements.csv` is absent before the pull.

```
make dvc-pull
...
A       data/measurements.csv
A       data/processed/test.csv
A       data/processed/train.csv
A       models/model.pkl
4 files fetched and 4 files added

md5sum data/measurements.csv
aed18119c18a85d1baae62dc4213b6a2  data/measurements.csv

grep md5 data/measurements.csv.dvc
- md5: aed18119c18a85d1baae62dc4213b6a2
```

The md5 of the pulled file equals the md5 in the pointer.

## R5 Two dataset versions

What changed and why. The full dataset was split at random into two raw batches with `scripts/split_batches.py` (60 percent and 40 percent, seed 42). `batch_01_baseline.csv` has 4925 rows and `batch_02_new_arrival.csv` has 3284 rows. Dataset version 1 is built from the first batch, and version 2 from both, so the second batch plays the part of a new arrival. Both batches are committed, and each version has its own pointer commit.

| Version | Commit | md5 | Lines in the file |
|---|---|---|---|
| 1, first batch | `220d618` | `58f6a205293130c4fe23f801e9babf9a` | 4926 |
| 2, both batches | `e55d1ea` | `aed18119c18a85d1baae62dc4213b6a2` | 8210 |

An earlier pointer exists in commit `a4e1c0c` with md5 `3ffd6a52c2cb7792bf4d036b22cfd193`. It named the same 8209 rows in their original order, which is the data the first registered model trained on. Version 2 holds the same rows in batch order, so its md5 differs.

Moving between the versions

```
git checkout 220d618 -- data/measurements.csv.dvc
uv run dvc checkout
md5sum data/measurements.csv
```

The recorded output

```
aed18119c18a85d1baae62dc4213b6a2  data/measurements.csv
- md5: aed18119c18a85d1baae62dc4213b6a2
8210 data/measurements.csv
M       data/measurements.csv
58f6a205293130c4fe23f801e9babf9a  data/measurements.csv
- md5: 58f6a205293130c4fe23f801e9babf9a
4926 data/measurements.csv
M       data/measurements.csv
aed18119c18a85d1baae62dc4213b6a2  data/measurements.csv
```

The first three lines are version 2 before the move. After the checkout the file is version 1, and after `git checkout HEAD -- data/measurements.csv.dvc` with another `dvc checkout` it is back on version 2 with the same md5.

## R6 The declared pipeline

`dvc.yaml` declares the stages `validate`, `prepare`, `train`, `evaluate` and `gate`. Every `cmd` is a `uv run python src/main.py <stage>` call that can also be run by hand. The source files are listed in `deps`, hyperparameters live in `params.yaml`, `metrics/metrics.json` and `metrics/slices.json` are `cache: false` outputs, and `dvc.lock` is committed.

Changing one parameter. `acceptance.criteria_version` went from `1.0.0` to `1.1.0` (together with `acceptance.slice_rules.min_support` from 30 to 50, because the group with a missing `Visibility_m` had only 33 test rows). Only the `gate` stage depends on the `acceptance` block, and only it re-ran.

```
make repro
'data/measurements.csv.dvc' didn't change, skipping
Stage 'validate' didn't change, skipping
Stage 'prepare' didn't change, skipping
Stage 'train' didn't change, skipping
Stage 'evaluate' didn't change, skipping
Running stage 'gate':
> uv run python src/main.py gate
GO — 21 passed, 0 failed, 1 SKIPPED (criteria v1.1.0)
```

Running it again changes nothing.

```
make repro
'data/measurements.csv.dvc' didn't change, skipping
Stage 'validate' didn't change, skipping
Stage 'prepare' didn't change, skipping
Stage 'train' didn't change, skipping
Stage 'evaluate' didn't change, skipping
Stage 'gate' didn't change, skipping
Data and pipelines are up to date.
```

## R7 MLflow tracking and the registry

TODO the table of at least four runs with more than one hyperparameter setting, the reasoning about the best one, the registered version with its `run_id`.

## R8 The data version on the run

TODO the `runs-for-data` output for a dataset md5.

## R9 The traceability chain

TODO the chain from the alias to the remote URI, with the values from `make trace`.

## R10 The hardest thing

The hardest problem was further understanding the structure and components of the lab to use as a skeleton for my implementation. After i cleared up missconceptions in my mind, everything was straight forward. I used Claude to rewrite lab sources for the regression task.
