import unittest
from calculator import InsuranceCalculator

class TestInsuranceCalculator(unittest.TestCase):
    def setUp(self):
        # Setup with a standard profile: 30 year old male
        self.calc = InsuranceCalculator(age=30, gender='male', inflation_rate=6.0)

    def test_term_premium_estimation(self):
        # 30yr Male, 1Cr Sum Assured, 30 Year Term
        # Base (at 25) = 100/lakh.
        # Age Factor = 1.05^(30-25) = 1.05^5 ≈ 1.276
        # Premium/Lakh = 100 * 1.276 ≈ 127.6
        # Total for 100 Lakhs = 12,760
        
        premium = self.calc.estimate_term_premium(10000000, 30)
        # Allow some margin for floating point math
        self.assertTrue(12000 < premium < 13500, f"Premium {premium} out of expected range")

    def test_term_premium_female_discount(self):
        calc_female = InsuranceCalculator(age=30, gender='female')
        premium_male = self.calc.estimate_term_premium(10000000, 30)
        premium_female = calc_female.estimate_term_premium(10000000, 30)
        
        # Female premium should be ~90% of Male
        self.assertTrue(premium_female < premium_male)
        self.assertAlmostEqual(premium_female/premium_male, 0.9, delta=0.01)

    def test_future_value_annuity_due(self):
        # Invest 100,000 per year for 10 years at 10%
        # Formula: P * ((1+r)^n - 1)/r * (1+r)
        # 100000 * (1.59374 - 1)/0.1 * 1.1
        # 100000 * 5.9374 * 1.1 = 100000 * 6.531... wait.
        # (1.1^10 - 1)/0.1 = 15.937
        # 15.937 * 1.1 = 17.53
        # FV should be ~17.53 Lakhs
        
        fv = self.calc.calculate_future_value(100000, 10, 10)
        expected = 100000 * (((1.1 ** 10) - 1) / 0.1) * 1.1
        self.assertAlmostEqual(fv, round(expected, 2), delta=1.0)

    def test_comparison_logic(self):
        # Sanity check: If returns are high, BTIR should win
        # Premium 1L, Term 20y, Maturity 40L (approx 5-6% return)
        # Market Return 12%
        results = self.calc.get_comparison(100000, 20, 20, 4000000, 12)
        
        btir_val = results['btir_final_value']
        # 12% should definitely beat the implicit ~5% of endowment
        self.assertTrue(btir_val > 4000000, "BTIR should beat Endowment at 12% return")

if __name__ == '__main__':
    unittest.main()
