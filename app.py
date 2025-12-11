from flask import Flask, render_template, request
import plotly.graph_objects as go
import pandas as pd
from calculator import InsuranceCalculator

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            form_type = request.form.get('form_type', 'comparison')
            
            # Common Inputs for both modes might exist, but strict separation is safer
            age = int(request.form.get('age', 30))
            gender = request.form.get('gender', 'male')
            inflation_rate = float(request.form.get('inflation_rate', 6.0))
            tax_bracket = float(request.form.get('tax_bracket', 30.0))
            capital_gains_tax = float(request.form.get('capital_gains_tax', 12.5))
            
            calc = InsuranceCalculator(age, gender, inflation_rate, tax_bracket, capital_gains_tax)

            if form_type == 'goal_planning':
                target_amount = float(request.form['target_amount'])
                years = int(request.form['goal_years'])
                return_rate = float(request.form['goal_return_rate'])
                
                annual_sip = calc.calculate_goal_requirements(target_amount, years, return_rate)
                monthly_sip = annual_sip / 12
                
                # Comparison: How much endowment premium needed? (Assuming 5% return approx)
                endowment_premium_needed = calc.calculate_goal_requirements(target_amount, years, 5.0)
                
                return render_template('result_goal.html', 
                                       target=target_amount, 
                                       years=years,
                                       annual_sip=annual_sip,
                                       monthly_sip=monthly_sip,
                                       endowment_premium=endowment_premium_needed)

            else: # Comparison Mode
                premium = float(request.form['premium'])
                premium_term = int(request.form['premium_term'])
                total_term = int(request.form['total_term'])
                maturity = float(request.form['maturity'])
                investment_return_rate = float(request.form['return_rate'])

                if premium_term > total_term:
                    return render_template('index.html', error="Premium term cannot exceed policy term.")

                # Calculations
                # Note: sum_assured usually ~10x premium or passed explicitly. We'll assume 10x for rule of thumb or same as maturity for endowment (often SA ~= Maturity or close).
                # Actually, let's assume Sum Assured = Maturity or Premium * 10, whichever higher.
                sum_assured = max(maturity, premium * 10) 
                
                results = calc.get_comparison(premium, premium_term, total_term, sum_assured, maturity, investment_return_rate)
                endowment_irr = calc.calculate_irr(premium, premium_term, total_term, maturity)
                
                # Liquidity Schedule
                liquidity = calc.calculate_liquidity_schedule(premium, premium_term, total_term, investment_return_rate, results['investable_surplus'])

                # Comparison Data
                real_value_endowment = calc.calculate_real_value(results['endowment_post_tax'], total_term)
                real_value_btir = calc.calculate_real_value(results['btir_post_tax'], total_term)
                
                opportunity_cost = results['btir_post_tax'] - results['endowment_post_tax']
                
                # Charts
                # 1. Bar Chart: Post-Tax vs Investment
                fig_bar = go.Figure(data=[
                    go.Bar(name='Endowment (Post-Tax)', x=['Final Value'], 
                           y=[results['endowment_post_tax']], marker_color='#ff6b6b'),
                    go.Bar(name='Buy Term + Invest (Post-Tax)', x=['Final Value'], 
                           y=[results['btir_post_tax']], marker_color='#51cf66')
                ])
                fig_bar.update_layout(barmode='group', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                      font=dict(color='#7d7d7d'), margin=dict(t=30, b=0, l=0, r=0))

                # 2. Liquidity Curve (Area Chart)
                fig_area = go.Figure()
                fig_area.add_trace(go.Scatter(x=liquidity['years'], y=liquidity['surrender_values'], stackgroup='one', name='Endowment Liquidity', line=dict(color='#ff6b6b')))
                fig_area.add_trace(go.Scatter(x=liquidity['years'], y=liquidity['mf_values'], stackgroup='two', name='Mutual Fund Liquidity', line=dict(color='#51cf66')))
                fig_area.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                       font=dict(color='#7d7d7d'), margin=dict(t=30, b=0, l=0, r=0),
                                       title="Liquidity Access (Cash Available)")

                return render_template('result.html',
                                       irr=endowment_irr,
                                       term_cost=results['term_cost'],
                                       investable_surplus=results['investable_surplus'],
                                       maturity=maturity,
                                       btir_value=results['btir_final_value'],
                                       btir_post_tax=results['btir_post_tax'],
                                       endowment_post_tax=results['endowment_post_tax'],
                                       tax_paid_endowment=results['endowment_tax_paid'],
                                       tax_paid_btir=results['btir_tax_paid'],
                                       is_taxable=results['is_taxable_endowment'],
                                       opportunity_cost=opportunity_cost,
                                       real_endowment=real_value_endowment,
                                       real_btir=real_value_btir,
                                       capital_gains_tax=capital_gains_tax,
                                       tax_bracket=tax_bracket,
                                       chart_bar=fig_bar.to_json(),
                                       chart_area=fig_area.to_json())

        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template('index.html', error=f"Error: {str(e)}")

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)