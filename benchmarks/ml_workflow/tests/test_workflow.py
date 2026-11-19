import tempfile
from pathlib import Path
import unittest
import numpy as np
from workflow import Features, assert_disjoint, dataset, fairness, save, split_indices, train, validate


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.report, cls.sample = train()

    def test_real_models_tuning_and_appropriate_imbalance_metrics(self):
        self.assertEqual(set(self.report['comparison']), {'logistic','forest'})
        for candidate in self.report['comparison'].values():
            self.assertGreaterEqual(candidate['cv_average_precision'],0)
            self.assertTrue(candidate['parameters'])
        self.assertLess(self.report['test_positive_fraction'],.3)
        self.assertTrue(all(0 <= value <= 1 for value in self.report['test'].values()))

    def test_stratified_reproducible_disjoint_splits(self):
        _,y,_=dataset();one=split_indices(y,23);two=split_indices(y,23)
        for a,b in zip(one,two):np.testing.assert_array_equal(a,b)
        assert_disjoint(*one)
        self.assertEqual(len(set().union(*map(set,one))),len(y))
        for chosen in one:self.assertGreaterEqual(np.bincount(y[chosen]).min(),3)

    def test_preprocessing_fit_uses_training_rows_and_training_quantiles(self):
        x,_,_=dataset();ids=self.report['splits']['train'];stage=self.model.named_steps['features']
        self.assertEqual(stage.fit_rows_,len(ids))
        np.testing.assert_allclose(stage.upper_,np.nanquantile(x[ids],.99,axis=0))
        self.assertTrue(np.isnan(x).any());self.assertTrue(np.isfinite(self.model.predict_proba(self.sample)).all())

    def test_outliers_and_feature_interaction(self):
        stage=Features().fit(np.array([[1.,2.],[2.,3.],[3.,4.]]));out=stage.transform(np.array([[1e8,2.]]))
        self.assertEqual(out.shape,(1,3));self.assertLess(out[0,0],4)

    def test_overlap_and_exact_target_leakage_refused(self):
        with self.assertRaisesRegex(ValueError,'overlap'):assert_disjoint([1,2],[2],[3])
        x,y,g=dataset();x[:,0]=y
        with self.assertRaisesRegex(ValueError,'leakage'):validate(x,y,g)

    def test_invalid_input_refused(self):
        x,y,g=dataset()
        with self.assertRaises(ValueError):validate(x[:-1],y,g)
        x[:,0]=np.nan
        with self.assertRaises(ValueError):validate(x,y,g)
        with self.assertRaises(ValueError):dataset(rows=2001)

    def test_fairness_denominators_and_empty_positives(self):
        result=fairness(np.array([1,0,0,0]),np.array([.9,.9,.1,.1]),np.array([0,0,1,1]))
        self.assertEqual(result['groups']['0']['true_positive_rate'],1.)
        self.assertIsNone(result['groups']['1']['true_positive_rate'])
        self.assertIsNone(result['tpr_gap'])
        self.assertIn('small subgroup',result['interpretation'])

    def test_explanation_drift_and_artifact_reproducibility(self):
        self.assertEqual(len(self.report['explainability']['importance']),8)
        self.assertEqual(len(self.report['drift']['mean_difference']),8)
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'artifacts';save(destination,self.model,self.report,self.sample)
            self.assertEqual({p.name for p in destination.iterdir()},{'model.joblib','report.json','test_sample.npy','manifest.json'})

    def test_repeated_seed_reproduces_predictions(self):
        model,report,sample=train()
        np.testing.assert_allclose(self.model.predict_proba(self.sample),model.predict_proba(sample))
        self.assertEqual(report['selected'],self.report['selected'])


if __name__=='__main__':unittest.main()
