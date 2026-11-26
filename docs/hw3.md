# HW3 Documentation

## R1 Prefect flow

I used the same approach, as lab 8, treating 'make repro' as a single task.


## R2 Retry policy

### Task Retry Summary

| Task | Retries? | Policy | Reason |
| :--- | :--- | :--- | :--- |
| `build_dataset` | No | None | Reads local files; missing inputs are broken checkouts that retries will not fix. |
| `params_committed` | No | None | Local `git status` check; deterministic and non-transient. |
| `run_pipeline` | No | None | Runs `dvc repro`; deterministic code/data/gate failures repeat identically. |
| `read_params_used` | No | None | Reads local `dvc.lock` YAML; deterministic local file read. |
| `pull_data` | Yes | `NETWORK_RETRIES` (`retries=3`, `exponential_backoff(2)`, `jitter=0.5`) | Network `dvc pull` to object store can fail transiently and is idempotent by content hash. |
| `push_data` | Yes | `NETWORK_RETRIES` (`retries=3`, `exponential_backoff(2)`, `jitter=0.5`) | Network `dvc push` to object store can fail transiently and is idempotent by content hash. |
| `register_model` | Yes | `retries=2`, `exponential_backoff(2)` | Touches MLflow over the network, though model version creation is not idempotent. |
| `notify` | No | None | Writes local `reports/last_run.txt` on both success and failure paths. |

### Non-Idempotent Operation: `register_model`

- **Why it is not idempotent:** Each registration call creates a new model version in the MLflow registry. If MLflow commits a version but the response back to Prefect is lost, a retry treats the call as failed and registers a duplicate version pointing to the same `run_id`.
- **How it is handled:** `register_model` queries `MlflowClient.search_model_versions(...)` for `v.run_id == run_id` before calling `registry.register_best_model(...)` and returns an existing version if found. This narrows the duplicate window, though a race between check and commit can still occur because the MLflow registry lacks a true idempotency key.

## R3 Demonstrating parameter change effects

###  Running the flow manually with force

Flow runs, but states that params.yaml has uncommitted changes.

```
> make flow
uv run python src/main.py flow
16:27:09.013 | INFO    | Flow run 'cream-mosquito' - Beginning flow run 'cream-mosquito' for flow 'ambulance-response-time-training'

...

16:27:17.599 | INFO    | Task run 'notify-88b' - notify: GO — 21 passed, 0 failed, 1 skipped (criteria 1.1.0) | random_seed=42, train.family=hgb, train.l2_regularization=1.0, train.learning_rate=0.05, train.max_iter=300, train.max_leaf_nodes=30, train.min_samples_leaf=50 | params.yaml uncommitted
16:27:17.601 | INFO    | Task run 'notify-88b' - Finished in state Completed()
16:27:18.020 | INFO    | Flow run 'cream-mosquito' - Finished in state Completed()

flow finished — verdict GO
```

### Running the flow as schedule does

Flow fails, and explains why: params.yaml has uncommitted changes.

```
> make flow-committed
uv run python src/main.py flow --require-committed
16:29:28.351 | INFO    | Flow run 'peculiar-cockle' - Beginning flow run 'peculiar-cockle' for flow 'ambulance-response-time-training'

...


16:29:29.359 | ERROR   | Flow run 'peculiar-cockle' - Encountered exception during execution: RuntimeError('params.yaml has uncommitted changes. Commit them, or undo them with `git restore params.yaml`, before this run trains a model.')
Traceback (most recent call last):
  File "/home/csuszka/Documents/egyetem/mlops/mlops-hw-project/.venv/lib/python3.13/site-packages/prefect/flow_engine.py", line 1277, in run_context
    yield self
  File "/home/csuszka/Documents/egyetem/mlops/mlops-hw-project/.venv/lib/python3.13/site-packages/prefect/flow_engine.py", line 2030, in run_flow_sync
    engine.call_flow_fn()
    ~~~~~~~~~~~~~~~~~~~^^
  File "/home/csuszka/Documents/egyetem/mlops/mlops-hw-project/.venv/lib/python3.13/site-packages/prefect/flow_engine.py", line 1297, in call_flow_fn
    result = call_with_parameters(self.flow.fn, self.parameters)
  File "/home/csuszka/Documents/egyetem/mlops/mlops-hw-project/.venv/lib/python3.13/site-packages/prefect/utilities/callables/__init__.py", line 348, in call_with_parameters
    return fn(*args, **kwargs)
  File "/home/csuszka/Documents/egyetem/mlops/mlops-hw-project/src/mlops_project/flows.py", line 77, in training_flow
    raise RuntimeError(
    ...<2 lines>...
    )
RuntimeError: params.yaml has uncommitted changes. Commit them, or undo them with `git restore params.yaml`, before this run trains a model.
16:29:29.379 | INFO    | Flow run 'peculiar-cockle' - Finished in state Failed('Flow run encountered an exception: RuntimeError: params.yaml has uncommitted changes. Commit them, or undo them with `git restore params.yaml`, before this run trains a model.')

Cannot run `flow` yet:
  params.yaml has uncommitted changes. Commit them, or undo them with `git restore params.yaml`, before this run trains a model.

make: *** [Makefile:359: flow-committed] Error 1
```


### Running the flow as schedule, with committed params.yaml

With params.yaml changes committed, the flow runs successfully, states the params are committed.

```
> make flow-committed
uv run python src/main.py flow --require-committed
16:34:31.877 | INFO    | Flow run 'cyber-wolf' - Beginning flow run 'cyber-wolf' for flow 'ambulance-response-time-training'

...

16:34:40.288 | INFO    | Task run 'notify-6f9' - notify: GO — 21 passed, 0 failed, 1 skipped (criteria 1.1.0) | random_seed=42, train.family=hgb, train.l2_regularization=1.0, train.learning_rate=0.05, train.max_iter=300, train.max_leaf_nodes=30, train.min_samples_leaf=50 | params.yaml committed
16:34:40.288 | INFO    | Task run 'notify-6f9' - Finished in state Completed()
16:34:40.887 | INFO    | Flow run 'cyber-wolf' - Finished in state Completed()

flow finished — verdict GO

```

## R4 Demonstrating the schedule

I used the same command 'make serve' as lab 8.

'''
> make serve
uv run python src/main.py serve --cron "*/5 * * * *"
Serving scheduled training flow on cron `*/5 * * * *`.
Open the UI at http://127.0.0.1:5520 to watch it.
Ctrl-C to stop.
Your flow 'ambulance-response-time-training-with-pull' is being served and polling for scheduled runs!

To trigger a run for this flow, use the following command:

        $ prefect deployment run 'ambulance-response-time-training-with-pull/weekly-retrain'

You can also run your flow via the Prefect UI: http://127.0.0.1:5520/deployments/deployment/458607b0-67cf-408b-ac14-dfeb9e77f5d2

16:39:59.977 | INFO    | Flow run 'offbeat-penguin' - Beginning flow run 'offbeat-penguin' for flow 'ambulance-response-time-training-with-pull'
16:39:59.980 | INFO    | Flow run 'offbeat-penguin' - View at http://127.0.0.1:5520/runs/flow-run/01a21881-a9ba-7885-b296-54a06c5e0324
16:40:00.476 | INFO    | Task run 'pull_data-ceb' - Finished in state Completed()
16:40:00.537 | INFO    | Flow run 'vermilion-kangaroo' - Beginning subflow run 'vermilion-kangaroo' for flow 'ambulance-response-time-training'
16:40:00.537 | INFO    | Flow run 'vermilion-kangaroo' - View at http://127.0.0.1:5520/runs/flow-run/addd50fc-3cce-4cfd-8241-430388b1666b
16:40:00.546 | INFO    | Task run 'params_committed-650' - Finished in state Completed()
16:40:00.567 | INFO    | Task run 'build_dataset-d9b' - built 4925 rows -> measurements.csv
16:40:00.569 | INFO    | Task run 'build_dataset-d9b' - Finished in state Completed()
16:40:00.893 | INFO    | Task run 'run_pipeline-d1c' - 'data/measurements.csv.dvc' didn't change, skipping
16:40:00.893 | INFO    | Task run 'run_pipeline-d1c' - Stage 'validate' didn't change, skipping
16:40:00.893 | INFO    | Task run 'run_pipeline-d1c' - Stage 'prepare' didn't change, skipping
16:40:00.894 | INFO    | Task run 'run_pipeline-d1c' - Stage 'train' didn't change, skipping
16:40:00.894 | INFO    | Task run 'run_pipeline-d1c' - Stage 'evaluate' didn't change, skipping
16:40:00.894 | INFO    | Task run 'run_pipeline-d1c' - Stage 'gate' didn't change, skipping
16:40:00.894 | INFO    | Task run 'run_pipeline-d1c' - Data and pipelines are up to date.
16:40:00.895 | INFO    | Task run 'run_pipeline-d1c' - Finished in state Completed()
16:40:00.905 | INFO    | Task run 'read_params_used-ae1' - Finished in state Completed()
16:40:00.911 | INFO    | Task run 'notify-fee' - notify: GO — 21 passed, 0 failed, 1 skipped (criteria 1.1.0) | random_seed=42, train.family=hgb, train.l2_regularization=1.0, train.learning_rate=0.05, train.max_iter=300, train.max_leaf_nodes=30, train.min_samples_leaf=50 | params.yaml committed
16:40:00.912 | INFO    | Task run 'notify-fee' - Finished in state Completed()
16:40:01.538 | INFO    | Flow run 'vermilion-kangaroo' - Finished in state Completed()
16:40:02.154 | INFO    | Flow run 'offbeat-penguin' - Finished in state Completed()

'''

## R5 Demonstrating the quality gate

A flow logs all the dvc stages that run, were skipped or the dvc stages that failed.
The following flow was ran after 'max_iter' in 'params.yaml' was changed to 1, resulting in a model with poor performance.

```
make flow
uv run python src/main.py flow
17:47:13.749 | INFO    | Flow run 'nimble-chimera' - Beginning flow run 'nimble-chimera' for flow 'ambulance-response-time-training'
17:47:13.753 | INFO    | Flow run 'nimble-chimera' - View at http://127.0.0.1:5520/runs/flow-run/cd7eecd1-1669-4fa9-9b25-6a5237e4fe36
17:47:13.766 | INFO    | Task run 'params_committed-1c2' - Finished in state Completed()
17:47:13.794 | INFO    | Task run 'build_dataset-5a4' - built 4925 rows -> measurements.csv
17:47:13.795 | INFO    | Task run 'build_dataset-5a4' - Finished in state Completed()
17:47:21.929 | INFO    | Task run 'run_pipeline-e2e' - 'data/measurements.csv.dvc' didn't change, skipping
17:47:21.930 | INFO    | Task run 'run_pipeline-e2e' - Stage 'validate' didn't change, skipping
17:47:21.930 | INFO    | Task run 'run_pipeline-e2e' - Stage 'prepare' didn't change, skipping
17:47:21.931 | INFO    | Task run 'run_pipeline-e2e' - Running stage 'train':
17:47:21.931 | INFO    | Task run 'run_pipeline-e2e' - > uv run python src/main.py train
17:47:21.931 | INFO    | Task run 'run_pipeline-e2e' - 🏃 View run dvc-hgb at: http://127.0.0.1:5500/#/experiments/1/runs/a101bbce8f9b47d6816a8377e15159f2
17:47:21.931 | INFO    | Task run 'run_pipeline-e2e' - 🧪 View experiment at: http://127.0.0.1:5500/#/experiments/1
17:47:21.931 | INFO    | Task run 'run_pipeline-e2e' - train: wrote /home/csuszka/Documents/egyetem/mlops/mlops-hw-project/models/model.pkl
17:47:21.932 | INFO    | Task run 'run_pipeline-e2e' -   MLflow run    : a101bbce8f9b47d6816a8377e15159f2
17:47:21.932 | INFO    | Task run 'run_pipeline-e2e' -   MLflow digest : aabb636d
17:47:21.932 | INFO    | Task run 'run_pipeline-e2e' -   DVC md5       : 58f6a205293130c4fe23f801e9babf9a
17:47:21.932 | INFO    | Task run 'run_pipeline-e2e' -   These describe the same file and they do not match.
17:47:21.933 | INFO    | Task run 'run_pipeline-e2e' -   MLflow's digest hashes PARSED VALUES of the first 10,000
17:47:21.933 | INFO    | Task run 'run_pipeline-e2e' -   rows plus the row count and column names, truncated to 8
17:47:21.933 | INFO    | Task run 'run_pipeline-e2e' -   characters. DVC's md5 hashes the FILE'S BYTES, all 32.
17:47:21.933 | INFO    | Task run 'run_pipeline-e2e' -   Only one of them proves 'these exact bytes'.
17:47:21.934 | INFO    | Task run 'run_pipeline-e2e' - Updating lock file 'dvc.lock'
17:47:21.934 | INFO    | Task run 'run_pipeline-e2e' - Running stage 'evaluate':
17:47:21.934 | INFO    | Task run 'run_pipeline-e2e' - > uv run python src/main.py evaluate
17:47:21.934 | INFO    | Task run 'run_pipeline-e2e' - evaluate:
17:47:21.934 | INFO    | Task run 'run_pipeline-e2e' - {
17:47:21.934 | INFO    | Task run 'run_pipeline-e2e' -   "rmse": 7.6283,
17:47:21.935 | INFO    | Task run 'run_pipeline-e2e' -   "mae": 6.0735,
17:47:21.935 | INFO    | Task run 'run_pipeline-e2e' -   "r2": 0.0752
17:47:21.935 | INFO    | Task run 'run_pipeline-e2e' - }
17:47:21.935 | INFO    | Task run 'run_pipeline-e2e' -   12 slice group(s) across 4 axes -> metrics/slices.json
17:47:21.935 | INFO    | Task run 'run_pipeline-e2e' -   metrics also logged to MLflow run a101bbce8f9b47d6816a8377e15159f2
17:47:21.935 | INFO    | Task run 'run_pipeline-e2e' - Updating lock file 'dvc.lock'
17:47:21.936 | INFO    | Task run 'run_pipeline-e2e' - Running stage 'gate':
17:47:21.936 | INFO    | Task run 'run_pipeline-e2e' - > uv run python src/main.py gate
17:47:21.936 | INFO    | Task run 'run_pipeline-e2e' - Cannot run `gate` yet:
17:47:21.936 | INFO    | Task run 'run_pipeline-e2e' -   NO-GO. 16 acceptance criteria failed: minimum.r2, maximum.mae, maximum.rmse, regression.rmse, slice.weather.clear, slice.weather.fog, slice.weather.rain, slice.weather.snow, slice.area_type.rural, slice.area_type.urban, slice.dispatch_priority.high, slice.dispatch_priority.medium, slice.dispatch_priority.standard, slice.visibility_missing.visibility_present, fairness.area_type.rmse_gap, fairness.area_type.mae_gap. See reports/gate.json for the numbers, or run `make gate` to print them. The model is still on disk — a failing gate stops a release, not an investigation.
```

## R7 Run history

There were 63 flow runs and 237 task runs so far.

'docs/screenshots/HW2' shows the UI, and the flow that contained retried tasks. The deployment schedule is also listed.

## R8 What the orchestrator cannot tell

Prefect records that a run happened, in which state, with how many attempts. It does not know what the run meant.

- **A refused model and a crash look the same.** `run_pipeline` raises an error whenever `dvc repro` exits with a non-zero code. The gate exits non-zero on a NO-GO, so a model refused by the gate (the `max_iter` 1 run, RMSE 7.59) and a broken DVC call both end as a failed task. Only the verdict file and the failure record tell them apart.

- **The notification goes nowhere.** `notify` writes a file on the machine that runs the flow. If that machine is down, or nobody opens the file, a failure is recorded but not seen.