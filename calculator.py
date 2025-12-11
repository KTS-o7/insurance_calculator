import numpy_financial as npf
import math

class InsuranceCalculator:
    def __init__(self, age, gender, inflation_rate=6.0, tax_bracket=30.0, capital_gains_tax=12.5):
        self.age = age
        self.gender = gender.lower()
        self.inflation_rate = inflation_rate
        self.tax_bracket = tax_bracket # For Endowments > 5L premium
        self.capital_gains_tax = capital_gains_tax
    
    def estimate_term_premium(self, sum_assured, term):
        """
        Estimate annual term insurance premium based on age, gender.
        Base rate assumption: ~1000 INR per 1Cr for a 25yr old male.
        """
        base_rate = 100.0 # Per Lakh Sum Assured for a 25 yr old male
        
        # Age mult
        age_factor = 1.05 ** (self.age - 25)
        
        # Gender discount
        gender_factor = 0.9 if self.gender == 'female' else 1.0
        
        estimated_premium_per_lakh = base_rate * age_factor * gender_factor
        
        total_premium = (sum_assured / 100000) * estimated_premium_per_lakh
        return round(total_premium, 2)

    def calculate_future_value(self, pmt, rate, years):
        """
        Calculate Future Value of an Annuity Due (investing at start of year).
        """
        r = rate / 100
        n = years
        if r == 0:
            return pmt * n
        fv = pmt * (((1 + r) ** n - 1) / r) * (1 + r)
        return round(fv, 2)

    def calculate_real_value(self, amount, years):
        """Discount future amount by inflation rate to get present purchasing power."""
        return round(amount / ((1 + self.inflation_rate/100) ** years), 2)
        
    def calculate_liquidity_schedule(self, premium, premium_term, total_term, investment_return_rate, investable_surplus):
        """
        Generate Year-wise Liquidity (Surrender Value vs Mutual Fund Value).
        """
        years = list(range(1, total_term + 1))
        
        surrender_values = []
        mf_values = []
        
        current_mf_corpus = 0
        total_premium_paid = 0
        
        for y in years:
            # 1. Mutual Fund Liquidity (100% accessible usually, maybe 1% exit load in yr 1)
            if y <= premium_term:
                current_mf_corpus = (current_mf_corpus + investable_surplus) * (1 + investment_return_rate/100)
            else:
                current_mf_corpus = current_mf_corpus * (1 + investment_return_rate/100)
            
            # Apply slight exit load if year 1 (1%)
            liquid_mf = current_mf_corpus * 0.99 if y == 1 else current_mf_corpus
            mf_values.append(round(liquid_mf, 2))
            
            # 2. Endowment Surrender Value
            if y <= premium_term:
                total_premium_paid += premium
            
            # Standard Surrender Rule estimation
            # Year 1-2: 0%
            # Year 3: 30% of premiums paid
            # Year 4-7: 50% of premiums paid
            # Year 7+: Gradually increases to 90%
            
            sv = 0
            if y < 3:
                sv = 0
            elif y == 3:
                sv = total_premium_paid * 0.30
            elif y < 7:
                sv = total_premium_paid * 0.50
            elif y < total_term:
                # Linear interpolation from 50% to 100% (at maturity)
                progress = (y - 7) / (total_term - 7)
                factor = 0.50 + (0.45 * progress) # Caps at ~95%
                sv = total_premium_paid * factor
            else:
                sv = total_premium_paid + (total_premium_paid * 0.5) # Maturity (just a placeholder, actual maturity logic is separate)
                
            surrender_values.append(round(sv, 2))
            
        return {
            "years": years,
            "surrender_values": surrender_values,
            "mf_values": mf_values
        }

    def get_comparison(self, endowment_premium, premium_term, total_term, sum_assured, maturity_amount, investment_return_rate):
        term_insurance_cost = self.estimate_term_premium(sum_assured, total_term)
        investable_surplus = endowment_premium - term_insurance_cost
        investable_surplus = max(0, investable_surplus)

        # Future Value of Investment
        fv_investment_phase = self.calculate_future_value(investable_surplus, investment_return_rate, premium_term)
        remaining_years = total_term - premium_term
        btir_final_value = fv_investment_phase * ((1 + investment_return_rate/100) ** remaining_years)
        
        # --- TAX CALCULATION ---
        # 1. Endowment
        total_endowment_paid = endowment_premium * premium_term
        endowment_gains = maturity_amount - total_endowment_paid
        endowment_tax = 0
        if endowment_premium > 500000:
            endowment_tax = endowment_gains * (self.tax_bracket / 100)
        
        endowment_post_tax = maturity_amount - endowment_tax
        
        # 2. BTIR (Mutual Funds)
        total_invested = investable_surplus * premium_term
        btir_gains = btir_final_value - total_invested
        # LTCG: Use user defined capital gains tax on gains
        btir_tax = max(0, btir_gains * (self.capital_gains_tax / 100))
        btir_post_tax = btir_final_value - btir_tax

        return {
            "term_cost": term_insurance_cost,
            "investable_surplus": investable_surplus,
            "btir_final_value": btir_final_value,
            "btir_post_tax": round(btir_post_tax, 2),
            "endowment_post_tax": round(endowment_post_tax, 2),
            "endowment_tax_paid": round(endowment_tax, 2),
            "btir_tax_paid": round(btir_tax, 2),
            "is_taxable_endowment": endowment_premium > 500000
        }

    def calculate_irr(self, premium, premium_term, total_term, maturity_amount):
        cashflows = [-premium] * premium_term
        cashflows.extend([0] * (total_term - premium_term))
        cashflows.append(maturity_amount)
        try:
            return round(npf.irr(cashflows) * 100, 2)
        except:
            return 0.0

    def calculate_goal_requirements(self, target_amount, years, return_rate):
        """
        Reverse Calculate: How much SIP/Premium needed to reach Goal?
        FV = P * ((1+r)^n - 1)/r * (1+r)
        P = FV / [ ((1+r)^n - 1)/r * (1+r) ]
        """
        r = return_rate / 100
        if r == 0:
            return round(target_amount / years, 2)
        
        factor = (((1 + r) ** years - 1) / r) * (1 + r)
        annual_investment_needed = target_amount / factor
        return round(annual_investment_needed, 2)
