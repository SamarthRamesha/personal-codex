"""Independent contrasts: group prevalence must not change the TPR denominator."""
import unittest
import numpy as np
from workflow import fairness


class FairnessDenominatorTests(unittest.TestCase):
    def test_false_positive_does_not_count_as_true_positive(self):
        result=fairness(np.array([1,0,0,0]),np.array([.1,.9,.1,.1]),np.array([0,0,1,1]))
        self.assertEqual(result['groups']['0']['selection_rate'],.5)
        self.assertEqual(result['groups']['0']['true_positive_rate'],0.)
        self.assertIsNone(result['groups']['1']['true_positive_rate'])

    def test_group_rates_and_gap_use_only_actual_positives(self):
        result=fairness(np.array([1,1,0,0,1,0]),np.array([.9,.1,.9,.9,.9,.1]),np.array([0,0,0,0,1,1]))
        self.assertEqual(result['groups']['0']['true_positive_rate'],.5)
        self.assertEqual(result['groups']['1']['true_positive_rate'],1.)
        self.assertEqual(result['tpr_gap'],.5)
        self.assertEqual(result['groups']['0']['selection_rate'],.75)

    def test_adding_negative_group_rows_cannot_change_tpr(self):
        first=fairness(np.array([1,1]),np.array([.9,.1]),np.array([0,0]))
        extra=fairness(np.array([1,1,0,0]),np.array([.9,.1,.9,.9]),np.array([0,0,0,0]))
        self.assertEqual(first['groups']['0']['true_positive_rate'],extra['groups']['0']['true_positive_rate'])


if __name__=='__main__':unittest.main()
