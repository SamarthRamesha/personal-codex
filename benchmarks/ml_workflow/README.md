# Synthetic ML workflow acceptance fixture

This is an independent bounded benchmark, not a production prediction service or a claim that the coding model generated every file. It uses installed NumPy, scikit-learn and joblib; these remain optional benchmark dependencies. No dataset/model download, cloud call, personal data or application dependency change is needed.

From a disposable copy of this directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 workflow.py --output artifacts
python3 -m http.server 8799 --bind 127.0.0.1
```

Open the loopback page to compare models, metrics, subgroup counts, permutation importance and descriptive mean shift. The server is only for the synthetic report; stop it with Ctrl-C. No frontend CDN or external request. Run the output command only against a new directory; artifacts are not overwritten. Reload only freshly generated trusted joblib artifacts, never untrusted uploaded pickle. The manifest identifies report/model/sample bytes; reproducibility is prediction-level, not an assertion that pickle bytes are stable across library versions.

The workflow generates bounded missing/outlier/imbalanced/noisy synthetic data, validates it, uses stratified train/validation/test splits, fits clipping/interaction/imputation/scaling inside cross-validation, tunes two classifiers, selects on validation average precision, evaluates a held-out test set, and exports model/report/test-sample/manifest. Fairness is descriptive with explicit small-sample limits. Exact target leakage and split overlap checks are deliberately limited; they cannot detect every proxy, temporal or domain leakage mechanism. Sensitive-group columns are excluded from features. Additional distribution-shift/high-dimensional/small/large fixtures are separate stress checks, not evidence of real-world validity.

The live agent exercise starts from a disposable copy with two deliberate defects in `split_indices` and `fairness`. It must repair existing production code while preserving this independent test suite. Retain failed attempts and actual model metrics. Do not attribute the scaffold or passing tests to model authorship.
