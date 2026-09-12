import unittest
from fm27.rating_calibration import attributes_for_variant,calibrated_level,family,fit_native_scale,holdout,quantile

class RatingCalibrationTests(unittest.TestCase):
    def test_monotonic_across_tied_anchors_and_tails(self):
        model=fit_native_scale([(50+i//10,55+i//10) for i in range(200)])
        values=[calibrated_level(model,i) for i in range(100)]
        self.assertEqual(values,sorted(values))
        self.assertTrue(all(abs(value-i)<=8 for i,value in enumerate(values)))

    def test_training_size_is_not_silently_relaxed(self):
        with self.assertRaises(ValueError): fit_native_scale([(50,60)]*99)

    def test_tail_limit_is_continuous_at_last_anchor(self):
        model={'anchors':[(40,40),(50,70)],'maximum_level_correction':40,
               'minimum_tail_slope':.5,'maximum_tail_slope':1.5}
        self.assertEqual(calibrated_level(model,50),70)
        self.assertEqual(calibrated_level(model,51),71.5)

    def test_constant_sample_rejected(self):
        with self.assertRaises(ValueError): fit_native_scale([(50,60)]*100)

    def test_quantile_interpolates_without_rounding_ratings(self):
        self.assertEqual(quantile([80,50,70,60],.25),57.5)

    def test_holdout_independent_of_input_order(self):
        identities=list(range(1,1000))
        a={i for i in identities if holdout(i)}
        b={i for i in reversed(identities) if holdout(i)}
        self.assertEqual(a,b)
        self.assertTrue(150<len(a)<250)

    def test_positions_group_roles_without_goalkeeper_fallback(self):
        self.assertEqual(family('CDM'),family('DM'))
        self.assertEqual(family('RM'),family('RW'))
        self.assertNotEqual(family('GK'),family('CB'))
        with self.assertRaises(ValueError): family('UNKNOWN')

    def test_attribute_cap_and_unchanged_fields(self):
        result=attributes_for_variant({'Pace':10,'Passing':98,'Corners':63},
            {'Pace':99,'Passing':1,'Corners':63},75,8)
        self.assertEqual(result,{'Pace':30,'Passing':78,'Corners':63})

    def test_integer_rounding_and_limits(self):
        self.assertEqual(attributes_for_variant({'Pace':50},{'Pace':51},50,0),{'Pace':51})
        with self.assertRaises(ValueError): attributes_for_variant({'Pace':50},{'Pace':100},75,0)
