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

Runs land in the experiment `ambulance-response-time` on the containerised MLflow server. Each run logs the hyperparameters, the test metrics and the model (`mlflow.sklearn.log_model`), and carries a `git_commit` tag. Only the hyperparameters that differ between runs are in the table. The others stay at `min_samples_leaf` 50 and `l2_regularization` 1.0. All five runs trained on dataset version 2 (md5 `aed18119c18a85d1baae62dc4213b6a2`) and were scored on the same 1642 test rows.

| Run | Commit | learning_rate | max_iter | max_leaf_nodes | RMSE | MAE | R2 | Gate |
|---|---|---|---|---|---|---|---|---|
| `97294783` baseline | `f0f3cf0` | 0.05 | 300 | 15 | 3.6521 | 2.8967 | 0.7859 | GO |
| `90ddd113` | `7464a0b` | 0.1 | 300 | 15 | 3.6977 | 2.9409 | 0.7805 | GO |
| `8316ec45` | `181134c` | 0.05 | 1 | 15 | 7.5917 | 5.9252 | 0.0748 | NO-GO |
| `b34e87a1` | `bfd0cba` | 0.05 | 300 | 31 | 3.7058 | 2.9463 | 0.7795 | GO |
| `7242d066` baseline again | `235ed5f` | 0.05 | 300 | 15 | 3.6521 | 2.8967 | 0.7859 | GO |

Which is best and on which metric. The primary metric is RMSE, because it is in minutes, the unit of the target, and it is the primary metric of the gate. The baseline setting is best on RMSE, and also on MAE and R2, so the three metrics agree. A higher learning rate and a bigger tree each made the model slightly worse, by about 0.05 minutes of RMSE. That is a small difference on a single test split of 1642 rows, so it should not be over-read, and the baseline stays the choice because it wins on every metric and needs no change. The run with `max_iter` 1 is a deliberately under-trained control. Its R2 of 0.07 shows a model that has barely learned anything, and the gate refused it with 16 of 22 checks failed. The two baseline runs have identical scores, so training is deterministic with the fixed seed. Three earlier runs, trained on the previous dataset md5, are also in the experiment and are not in this table.

TODO the registered version with its alias and its populated `run_id`, once the winning run is registered.

## R8 The data version on the run

Every training run carries the tags `dvc_md5`, `dvc_url`, `dvc_remote` and `data_file`, set from the DVC pointer when the run starts. The `runs-for-data` subcommand (`make runs-for-data`) reads the md5 from `data/measurements.csv.dvc` and lists every run in the experiment with that tag.

```
make runs-for-data
Searching for runs with tags.dvc_md5 = 'aed18119c18a85d1baae62dc4213b6a2'
                          run_id tags.mlflow.runName params.learning_rate  metrics.rmse tags.git_commit
7242d0667b344e55ad4b1d95fdacbc2b             dvc-hgb                 0.05        3.6521         235ed5f
b34e87a1f963463f83732623c21c6d1a             dvc-hgb                 0.05        3.7058         bfd0cba
8316ec4525b24f89ad3ba06c343dd977             dvc-hgb                 0.05        7.5917         181134c
90ddd113a6164b0d9034d90ed194e8b7             dvc-hgb                  0.1        3.6977         7464a0b
972947834d1f4a2ba87b9f05376770a2             dvc-hgb                 0.05        3.6521         f0f3cf0

  5 run(s).
```

The five runs are the first baseline run on this data (`97294783`), the `learning_rate` 0.1 run (`90ddd113`), the `max_iter` 1 run that the gate refused (`8316ec45`), the `max_leaf_nodes` 31 run (`b34e87a1`) and the restored baseline (`7242d066`). The two baseline runs have the same scores, so training is deterministic with the fixed seed. Runs trained on the earlier data, md5 `3ffd6a52c2cb7792bf4d036b22cfd193`, are not in this list..

## R9 The traceability chain

The winning run `7242d066` is registered as version 2 of `ambulance-response-regressor`. Registration refuses unless `reports/gate.json` records a GO, and the version is tagged with the verdict and the criteria version.

```
make register
Created version '2' of model 'ambulance-response-regressor'.
Registered ambulance-response-regressor version 2
  source run: 7242d0667b344e55ad4b1d95fdacbc2b
  gate      : GO (criteria v1.1.0)

make promote-champion
Version 2 now carries aliases: ['champion', 'staging']
```

The version's `run_id` is populated. It is the run `7242d0667b344e55ad4b1d95fdacbc2b` printed above, and the trace in R9 reads it back through the alias. Version 1 is the first registered model, from run `12cfd387` on the earlier dataset md5. It stays in the registry as history and no longer carries an alias.

── Traceability chain ──
1. Model URI    : models:/ambulance-response-regressor@staging
2. Version      : 2  (aliases: ['champion', 'staging'])
3. Run          : 7242d0667b344e55ad4b1d95fdacbc2b  (dvc-hgb)
4. Git commit   : 235ed5f
5. Data version : aed18119c18a85d1baae62dc4213b6a2
   Data location: s3://dvc-storage/dvcstore/files/md5/ae/d18119c18a85d1baae62dc4213b6a2
6. Validation   : pass  (contract v1.0.0, 0 failure case(s))
7. Params:
{
      "model_family": "hgb",
      "learning_rate": "0.05",
      "max_leaf_nodes": "15",
      "min_samples_leaf": "50",
      "l2_regularization": "1.0",
      "max_iter": "300",
      "random_seed": "42",
      "test_size": "0.2",
      "n_rows_train": "6567"
}
8. Gate         : GO  (criteria v1.1.0, 0 failed, 1 skipped)
   Champion     : version 2

## R10 The hardest thing

The hardest problem was further understanding the structure and components of the lab to use as a skeleton for my implementation. After i cleared up missconceptions in my mind, everything was straight forward. I used Claude to rewrite lab sources for the regression task.
