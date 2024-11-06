from flask import Flask, render_template, request, send_file
import numpy_financial as npf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import io

app = Flask(__name__)

class InsuranceCalculator:
    def __init__(self, fd_rate=6.5, debt_fund_rate=7.5, inflation_rate=5.0):
        self.fd_rate = fd_rate
        self.debt_fund_rate = debt_fund_rate
        self.inflation_rate = inflation_rate
        self.term_insurance_rate = 4.0  # per lakh per year
    
    def calculate_investment_returns(self, premium, premium_term, total_term, rate):
        """Calculate returns with limited premium payment term"""
        total_investment = premium * premium_term
        return round(total_investment * (1 + rate/100) ** total_term, 2)
    
    def calculate_fixed_deposit_returns(self, premium, premium_term, total_term, rate):
        rate = rate/100
        """Calculate returns with limited premium payment term"""
        total_investment = (premium/rate)*(1-(1+rate)**(-premium_term))
        total_investment = total_investment*(1+(rate))**(total_term-premium_term)
        return round(total_investment, 2)
    
    def calculate_endowment_irr(self, premium, premium_term, total_term, maturity_amount):
        """Calculate IRR with limited premium payment"""
        cashflows = [-premium] * premium_term
        cashflows.extend([0] * (total_term - premium_term))
        cashflows.append(maturity_amount)
        return round(npf.irr(cashflows) * 100, 2)
    
    def calculate_opportunity_cost(self, premium, premium_term, total_term, maturity_amount):
        """Calculate opportunity cost compared to better investments"""
        debt_fund_returns = self.calculate_fixed_deposit_returns( premium, premium_term, total_term, self.debt_fund_rate)
        opportunity_loss = debt_fund_returns
        return round(opportunity_loss, 2)
    
    def calculate_real_value(self, future_amount, term):
        """Calculate inflation-adjusted present value"""
        return round(future_amount / ((1 + self.inflation_rate/100) ** term), 2)
    
    def calculate_term_insurance_cost(self, sum_assured, term):
        """Calculate pure term insurance cost"""
        return round((sum_assured/100000) * self.term_insurance_rate * term, 2)
    
    def get_detailed_comparison(self, premium, premium_term, total_term, maturity):
        """Generate detailed comparison between different investment options"""
        term_insurance_cost = self.calculate_term_insurance_cost(maturity, total_term)
        investment_premium = premium - term_insurance_cost/premium_term
        
        data = {
            'Investment Type': ['Endowment Plan', 'Term + Debt Fund', 'Term + FD'],
            'Premium Payment Years': [premium_term] * 3,
            'Total Policy Term': [total_term] * 3,
            'Total_Premium_Paid': [premium * premium_term] * 3,
            'Insurance_Coverage': [maturity] * 3,
            'Final Amount': [
                maturity,
                self.calculate_fixed_deposit_returns(investment_premium, premium_term, total_term, self.debt_fund_rate)+maturity,
                self.calculate_fixed_deposit_returns(investment_premium, premium_term, total_term, self.fd_rate)+maturity
            ],
            'Real Value': [
                self.calculate_real_value(maturity, total_term),
                self.calculate_real_value(self.calculate_fixed_deposit_returns(investment_premium, premium_term, total_term, self.debt_fund_rate), total_term)+maturity,
                self.calculate_real_value(self.calculate_fixed_deposit_returns(investment_premium, premium_term, total_term, self.fd_rate), total_term)+maturity
            ],
        }
        return pd.DataFrame(data)

    def get_year_wise_comparison(self, premium, premium_term, total_term, maturity):
        """Generate year-by-year comparison data"""
        years = list(range(1, total_term + 1))
        endowment_values = [0] * (total_term - 1) + [maturity]
        
        debt_values = []
        for year in years:
            if year <= premium_term:
                debt_values.append(self.calculate_fixed_deposit_returns(
                    premium, year, year, self.debt_fund_rate)+maturity)
            else:
                debt_values.append(self.calculate_fixed_deposit_returns(
                    premium, premium_term, year, self.debt_fund_rate)+maturity)
        
        return pd.DataFrame({
            'Year': years,
            'Endowment Value': endowment_values,
            'Better Investment': debt_values,
            'Difference': [d - e for d, e in zip(debt_values, endowment_values)]
        })

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            premium = float(request.form['premium'])
            premium_term = int(request.form['premium_term'])
            total_term = int(request.form['total_term'])
            maturity = float(request.form['maturity'])
            inflation_rate = float(request.form['inflation_rate'])
            fd_rate = float(request.form['fd_rate'])
            debt_fund_rate = float(request.form['debt_rate'])
            
            
            if premium_term > total_term:
                return render_template('index.html', 
                    error="Premium payment term cannot exceed total policy term")
            
            calc = InsuranceCalculator(fd_rate=fd_rate, debt_fund_rate=debt_fund_rate, inflation_rate=inflation_rate)
            irr = calc.calculate_endowment_irr(premium, premium_term, total_term, maturity)
            detailed_comparison = calc.get_detailed_comparison(premium, premium_term, total_term, maturity)
            yearly_comparison = calc.get_year_wise_comparison(premium, premium_term, total_term, maturity)
            opportunity_cost = calc.calculate_opportunity_cost(premium, premium_term, total_term, maturity)
            
            # Create visualizations
            fig1 = go.Figure(data=[
                go.Bar(name='Final Amount', x=detailed_comparison['Investment Type'], 
                      y=detailed_comparison['Final Amount']),
                go.Bar(name='Real Value', x=detailed_comparison['Investment Type'], 
                      y=detailed_comparison['Real Value'])
            ])
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=yearly_comparison['Year'], 
                                    y=yearly_comparison['Endowment Value'],
                                    name='Endowment Plan'))
            fig2.add_trace(go.Scatter(x=yearly_comparison['Year'], 
                                    y=yearly_comparison['Better Investment'],
                                    name='Better Investment'))
            
            return render_template('result.html',
                                 irr=irr,
                                 opportunity_cost=opportunity_cost,
                                 detailed_comparison=detailed_comparison.to_dict('records'),
                                 yearly_comparison=yearly_comparison.to_dict('records'),
                                 chart1_json=fig1.to_json(),
                                 chart2_json=fig2.to_json())
        
        except ValueError as e:
            return render_template('index.html', 
                error="Please enter valid numeric values")
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)