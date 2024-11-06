import pytest
from app import InsuranceCalculator

def test_insurance_calculator():
    calc = InsuranceCalculator()
    
    # Test IRR calculation
    irr = calc.calculate_endowment_irr(premium=10000, term=10, maturity_amount=150000)
    assert isinstance(irr, float)
    assert irr > 0
    
    # Test investment returns
    fd_returns = calc.calculate_investment_returns(10000, 10, calc.fd_rate)
    assert isinstance(fd_returns, float)
    assert fd_returns > 100000
    
    # Test comparison data
    comparison = calc.get_comparison_data(10000, 10, 150000)
    assert len(comparison) == 3
    assert all(col in comparison.columns for col in ['Investment Type', 'Total Investment', 'Returns'])