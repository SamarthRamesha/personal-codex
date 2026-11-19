"""Synthetic, bounded tabular ML benchmark. No personal data or network access."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib


def dataset(seed=23, rows=320, features=8, minority=.18, noise=.03):
    if not 80 <= rows <= 2000 or not 6 <= features <= 40 or not .03 <= minority <= .5:
        raise ValueError('Dataset exceeds bounded benchmark envelope')
    x, y = make_classification(n_samples=rows, n_features=features, n_informative=4,
        n_redundant=0, weights=[1-minority, minority], flip_y=noise, random_state=seed)
    rng = np.random.default_rng(seed)
    group = rng.integers(0, 2, rows)
    x[rng.random(x.shape) < .06] = np.nan
    x[0, 0] = 1000
    return x, y, group


def validate(x, y, group):
    if x.ndim != 2 or len(x) != len(y) or len(y) != len(group) or len(y) < 60:
        raise ValueError('Mismatched or too-small dataset')
    if np.isinf(x).any() or set(np.unique(y)) != {0, 1} or set(np.unique(group)) != {0, 1}:
        raise ValueError('Invalid values or missing target/group classes')
    for column in x.T:
        if np.isfinite(column).sum() < 3 or np.array_equal(np.nan_to_num(column, nan=-9), y):
            raise ValueError('Empty feature or exact target leakage')


def split_indices(y, seed):
    indices = np.arange(len(y))
    train, rest = train_test_split(indices, test_size=.4, stratify=y, random_state=seed)
    valid, test = train_test_split(rest, test_size=.5, stratify=y[rest], random_state=seed)
    return train, valid, test


def assert_disjoint(train, valid, test):
    if set(train) & set(valid) or set(train) & set(test) or set(valid) & set(test):
        raise ValueError('Data leakage: split overlap')


class Features(BaseEstimator, TransformerMixin):
    def fit(self, x, y=None):
        self.lower_ = np.nanquantile(x, .01, axis=0)
        self.upper_ = np.nanquantile(x, .99, axis=0)
        self.fit_rows_ = len(x)
        return self

    def transform(self, x):
        clipped = np.clip(x, self.lower_, self.upper_)
        return np.column_stack([clipped, clipped[:, 0] * clipped[:, 1]])


def score(y, probabilities):
    return {'average_precision': float(average_precision_score(y, probabilities)),
        'roc_auc': float(roc_auc_score(y, probabilities)),
        'balanced_accuracy': float(balanced_accuracy_score(y, probabilities >= .5)),
        'brier': float(brier_score_loss(y, probabilities))}


def fairness(y, probabilities, group):
    report = {}
    for value in np.unique(group):
        chosen = group == value
        positive = chosen & (y == 1)
        report[str(value)] = {'n': int(chosen.sum()), 'positives': int(positive.sum()),
            'selection_rate': float(np.mean(probabilities[chosen] >= .5)),
            'true_positive_rate': float(np.mean(probabilities[positive] >= .5)) if positive.any() else None}
    rates = [row['true_positive_rate'] for row in report.values() if row['true_positive_rate'] is not None]
    return {'groups': report, 'tpr_gap': max(rates)-min(rates) if len(rates) == 2 else None,
        'interpretation': 'Descriptive synthetic audit; small subgroup counts do not establish fairness.'}


def train(seed=23, rows=320, features=8, minority=.18, noise=.03):
    x, y, group = dataset(seed, rows, features, minority, noise)
    validate(x, y, group)
    train_ids, valid_ids, test_ids = split_indices(y, seed)
    assert_disjoint(train_ids, valid_ids, test_ids)
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    candidates = {
        'logistic': (LogisticRegression(max_iter=200, class_weight='balanced', random_state=seed), {'model__C':[.1, 1.]}),
        'forest': (RandomForestClassifier(n_estimators=24, max_depth=4, class_weight='balanced', n_jobs=1, random_state=seed), {'model__min_samples_leaf':[2, 5]})}
    models, comparison = {}, {}
    for name, (classifier, parameters) in candidates.items():
        pipeline = Pipeline([('features', Features()), ('impute', SimpleImputer(strategy='median')),
                             ('scale', StandardScaler()), ('model', classifier)])
        search = GridSearchCV(pipeline, parameters, scoring='average_precision', cv=cv, n_jobs=1, error_score='raise')
        search.fit(x[train_ids], y[train_ids])
        models[name] = search.best_estimator_
        comparison[name] = {'cv_average_precision':float(search.best_score_), 'parameters':search.best_params_,
                           'validation':score(y[valid_ids], search.predict_proba(x[valid_ids])[:, 1])}
    selected = max(comparison, key=lambda name: comparison[name]['validation']['average_precision'])
    model = models[selected]
    predictions = model.predict_proba(x[test_ids])[:, 1]
    explanation = permutation_importance(model, x[valid_ids], y[valid_ids], n_repeats=3,
        random_state=seed, scoring='average_precision', n_jobs=1).importances_mean
    drift = np.nanmean(x[test_ids], axis=0)-np.nanmean(x[train_ids], axis=0)
    report = {'schema':1, 'seed':seed, 'rows':rows, 'features':features, 'selected':selected,
        'splits': {'train':train_ids.tolist(), 'validation':valid_ids.tolist(), 'test':test_ids.tolist()},
        'fit_rows':model.named_steps['features'].fit_rows_, 'comparison':comparison,
        'test':score(y[test_ids], predictions), 'test_positive_fraction':float(y[test_ids].mean()),
        'explainability':{'method':'validation permutation importance in average precision', 'importance':explanation.tolist()},
        'fairness':fairness(y[test_ids], predictions, group[test_ids]),
        'drift':{'mean_difference':drift.tolist(), 'interpretation':'Descriptive mean shift; no causal or safety claim.'},
        'limits':['Synthetic classification only', 'No external validation', 'Exact-target and index overlap checks cannot rule out every leakage mechanism'],
        'preview': [{'actual':int(label), 'probability':float(value)} for label,value in zip(y[test_ids][:12],predictions[:12])]}
    return model, report, x[test_ids]


def save(output, model, report, sample):
    output = Path(output)
    output.mkdir(mode=0o700)
    joblib.dump(model, output/'model.joblib')
    (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    np.save(output/'test_sample.npy', sample)
    files = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir() if path.is_file()}
    (output/'manifest.json').write_text(json.dumps({'seed':report['seed'],'files':files}, indent=2)+'\n')
    # Only reload this freshly generated trusted fixture artifact, never arbitrary uploaded pickle.
    restored = joblib.load(output/'model.joblib')
    if not np.allclose(model.predict_proba(sample), restored.predict_proba(sample)):
        raise ValueError('Artifact predictions do not reproduce')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path); parser.add_argument('--seed', type=int, default=23)
    args = parser.parse_args(); model, report, sample = train(args.seed)
    if args.output:
        save(args.output, model, report, sample)
    print('ML workflow verified')


if __name__ == '__main__':
    main()
