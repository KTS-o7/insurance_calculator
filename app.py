from flask import Flask, render_template, request, jsonify
import plotly.graph_objects as go
import pandas as pd
from calculator import InsuranceCalculator
from sip_calculator import SIPCalculator
from datetime import date, timedelta
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq Client
# Using user specified model or falling back to a versatile Llama model on Groq
GROQ_MODEL = "moonshotai/kimi-k2-instruct" 
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

app = Flask(__name__)

# Initialize SIP Calculator
sip_calc = SIPCalculator()

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
                                       endowment_premium=endowment_premium_needed,
                                       return_rate=return_rate)

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

                                       premium=premium,
                                       years=total_term,
                                       return_rate=investment_return_rate,
                                       chart_bar=fig_bar.to_json(),
                                       chart_area=fig_area.to_json())

        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template('index.html', error=f"Error: {str(e)}")

    return render_template('index.html')


# =============================================================================
# SIP ANALYZER ROUTES
# =============================================================================

@app.route('/sip', methods=['GET', 'POST'])
def sip_analyzer():
    """SIP Analysis with allocation backtesting"""
    presets = sip_calc.get_presets()
    asset_classes = sip_calc.get_asset_classes()
    
    if request.method == 'POST':
        try:
            # Get form data
            monthly_sip = float(request.form.get('monthly_sip', 10000))
            years = int(request.form.get('years', 5))
            allocation_mode = request.form.get('allocation_mode', 'preset')
            
            if allocation_mode == 'funds':
                # Fund-based allocation mode
                import json
                funds_json = request.form.get('funds_config', '{}')
                try:
                    funds_config = json.loads(funds_json)
                except:
                    funds_config = {}
                
                if not funds_config:
                    return render_template('index.html',
                                           error="Please select at least one fund",
                                           sip_tab=True, presets=presets, asset_classes=asset_classes)
                
                # Validate total allocation
                total_pct = 0
                for asset_class, funds in funds_config.items():
                    for fund in funds:
                        total_pct += fund.get('percentage', 0)
                
                if abs(total_pct - 100) > 0.01:
                    return render_template('index.html',
                                           error=f"Allocation must sum to 100%, got {total_pct:.1f}%",
                                           sip_tab=True, presets=presets, asset_classes=asset_classes)
                
                # Run fund-based analysis
                results = sip_calc.analyze_funds(funds_config, monthly_sip, years)
                
                # Create charts for fund-based results
                charts = create_sip_fund_charts(results, asset_classes)
                
                return render_template('result_sip.html',
                                       results=results,
                                       charts=charts,
                                       asset_classes=asset_classes)
            
            else:
                # Build allocation dict (preset or custom)
                if allocation_mode == 'preset':
                    preset_name = request.form.get('preset', 'balanced')
                    allocation = presets.get(preset_name, presets['balanced'])['allocation']
                else:
                    # Custom allocation from sliders
                    allocation = {}
                    for asset_class in asset_classes.keys():
                        pct = float(request.form.get(f'alloc_{asset_class}', 0))
                        if pct > 0:
                            allocation[asset_class] = pct
                
                # Validate allocation sums to 100
                total_alloc = sum(allocation.values())
                if abs(total_alloc - 100) > 0.01:
                    return render_template('index.html', 
                                           error=f"Allocation must sum to 100%, got {total_alloc:.1f}%",
                                           sip_tab=True, presets=presets, asset_classes=asset_classes)
                
                # Run analysis
                results = sip_calc.analyze_allocation(allocation, monthly_sip, years)
                
                # Create charts
                charts = create_sip_charts(results, asset_classes)
                
                return render_template('result_sip.html',
                                       results=results,
                                       charts=charts,
                                       asset_classes=asset_classes)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template('index.html', 
                                   error=f"Error: {str(e)}", 
                                   sip_tab=True, presets=presets, asset_classes=asset_classes)
    
    return render_template('index.html', sip_tab=False, presets=presets, asset_classes=asset_classes)


def create_sip_charts(results: dict, asset_classes: dict) -> dict:
    """Create Plotly charts for SIP results"""
    charts = {}
    
    # 1. Allocation Donut Chart
    alloc_results = results.get('allocation_results', {})
    if alloc_results:
        labels = [v['label'] for v in alloc_results.values()]
        values = [v['percentage'] for v in alloc_results.values()]
        colors = [v['color'] for v in alloc_results.values()]
        
        fig_donut = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='outside'
        )])
        fig_donut.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#7d7d7d'),
            margin=dict(t=30, b=30, l=30, r=30),
            showlegend=False
        )
        charts['allocation'] = fig_donut.to_json()
    
    # 2. Returns Comparison Bar Chart (Portfolio vs Benchmark)
    fig_returns = go.Figure(data=[
        go.Bar(
            name='Your Portfolio',
            x=['Total Return'],
            y=[results.get('return_pct', 0)],
            marker_color='#51cf66'
        ),
        go.Bar(
            name='Nifty 50 Benchmark',
            x=['Total Return'],
            y=[results.get('benchmark_return', 0)],
            marker_color='#4a90e2'
        )
    ])
    fig_returns.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#7d7d7d'),
        margin=dict(t=30, b=30, l=50, r=30),
        yaxis_title='Return (%)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    charts['returns'] = fig_returns.to_json()
    
    # 3. Asset-wise Performance Breakdown
    if alloc_results:
        asset_labels = [v['label'] for v in alloc_results.values()]
        asset_returns = [v['return_pct'] for v in alloc_results.values()]
        asset_colors = [v['color'] for v in alloc_results.values()]
        
        fig_breakdown = go.Figure(data=[go.Bar(
            x=asset_labels,
            y=asset_returns,
            marker_color=asset_colors,
            text=[f"{r:.1f}%" for r in asset_returns],
            textposition='outside'
        )])
        fig_breakdown.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#7d7d7d'),
            margin=dict(t=30, b=60, l=50, r=30),
            yaxis_title='Return (%)',
            xaxis_tickangle=-45
        )
        charts['breakdown'] = fig_breakdown.to_json()
    
    return charts


def create_sip_fund_charts(results: dict, asset_classes: dict) -> dict:
    """Create Plotly charts for fund-based SIP results"""
    charts = {}
    
    alloc_results = results.get('allocation_results', {})
    
    # 1. Allocation Donut Chart (by asset class)
    if alloc_results:
        labels = [v['label'] for v in alloc_results.values()]
        # Calculate percentage from actual invested amounts
        total_invested = sum(v.get('total_invested', 0) for v in alloc_results.values())
        values = [v.get('total_invested', 0) / total_invested * 100 if total_invested > 0 else 0 
                  for v in alloc_results.values()]
        colors = [v['color'] for v in alloc_results.values()]
        
        fig_donut = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='outside'
        )])
        fig_donut.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#7d7d7d'),
            margin=dict(t=30, b=30, l=30, r=30),
            showlegend=False
        )
        charts['allocation'] = fig_donut.to_json()
    
    # 2. Returns Comparison Bar Chart (Portfolio vs Benchmark)
    fig_returns = go.Figure(data=[
        go.Bar(
            name='Your Portfolio',
            x=['Total Return'],
            y=[results.get('return_pct', 0)],
            marker_color='#51cf66'
        ),
        go.Bar(
            name='Nifty 50 Benchmark',
            x=['Total Return'],
            y=[results.get('benchmark_return', 0)],
            marker_color='#4a90e2'
        )
    ])
    fig_returns.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#7d7d7d'),
        margin=dict(t=30, b=30, l=50, r=30),
        yaxis_title='Return (%)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    charts['returns'] = fig_returns.to_json()
    
    # 3. Individual Fund Performance Breakdown
    fund_results = results.get('fund_results', {})
    if fund_results:
        fund_names = [f.get('name', f.get('scheme_code', 'Unknown'))[:20] + '...' 
                      if len(f.get('name', '')) > 20 else f.get('name', f.get('scheme_code', 'Unknown'))
                      for f in fund_results.values()]
        fund_returns = [f.get('return_pct', 0) for f in fund_results.values()]
        
        # Color gradient for funds
        fund_colors = ['#4a90e2', '#7c3aed', '#ec4899', '#10b981', '#f59e0b', '#06b6d4'][:len(fund_names)]
        
        fig_funds = go.Figure(data=[go.Bar(
            x=fund_names,
            y=fund_returns,
            marker_color=fund_colors,
            text=[f"{r:.1f}%" for r in fund_returns],
            textposition='outside'
        )])
        fig_funds.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#7d7d7d'),
            margin=dict(t=30, b=80, l=50, r=30),
            yaxis_title='Return (%)',
            xaxis_tickangle=-45
        )
        charts['breakdown'] = fig_funds.to_json()
    
    # 4. Asset-wise Performance Breakdown (fallback if no individual funds)
    elif alloc_results:
        asset_labels = [v['label'] for v in alloc_results.values()]
        asset_returns = [v['return_pct'] for v in alloc_results.values()]
        asset_colors = [v['color'] for v in alloc_results.values()]
        
        fig_breakdown = go.Figure(data=[go.Bar(
            x=asset_labels,
            y=asset_returns,
            marker_color=asset_colors,
            text=[f"{r:.1f}%" for r in asset_returns],
            textposition='outside'
        )])
        fig_breakdown.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#7d7d7d'),
            margin=dict(t=30, b=60, l=50, r=30),
            yaxis_title='Return (%)',
            xaxis_tickangle=-45
        )
        charts['breakdown'] = fig_breakdown.to_json()
    
    return charts


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/api/schemes/search')
def api_search_schemes():
    """Search mutual fund schemes"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    schemes = sip_calc.search_schemes(query)
    return jsonify(schemes[:20])  # Limit to 20 results


@app.route('/api/fund/<isin>/details')
def api_fund_details(isin):
    """Get fund details from Captnemo API"""
    details = sip_calc.get_fund_details(isin)
    return jsonify(details)


@app.route('/api/presets')
def api_get_presets():
    """Get allocation presets"""
    return jsonify(sip_calc.get_presets())


@app.route('/api/asset-classes')
def api_get_asset_classes():
    """Get available asset classes"""
    return jsonify(sip_calc.get_asset_classes())


@app.route('/api/allocation/backtest', methods=['POST'])
def api_backtest_allocation():
    """Backtest a custom allocation"""
    try:
        data = request.get_json()
        allocation = data.get('allocation', {})
        monthly_sip = float(data.get('monthly_sip', 10000))
        years = int(data.get('years', 5))
        
        results = sip_calc.analyze_allocation(allocation, monthly_sip, years)
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/sip/analyze-funds', methods=['POST'])
def api_analyze_funds():
    """Analyze SIP with specific mutual funds"""
    try:
        data = request.get_json()
        funds_config = data.get('funds', {})
        monthly_sip = float(data.get('monthly_sip', 10000))
        years = int(data.get('years', 5))
        
        if not funds_config:
            return jsonify({'error': 'No funds configuration provided'}), 400
        
        # Validate total allocation
        total_pct = 0
        for asset_class, funds in funds_config.items():
            for fund in funds:
                total_pct += fund.get('percentage', 0)
        
        if abs(total_pct - 100) > 0.01:
            return jsonify({'error': f'Total allocation must be 100%, got {total_pct}%'}), 400
        
        results = sip_calc.analyze_funds(funds_config, monthly_sip, years)
        return jsonify(results)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


@app.route('/api/sip/compare', methods=['POST'])
def api_compare_portfolios():
    """Compare two portfolio configurations"""
    try:
        data = request.get_json()
        portfolio_a = data.get('portfolio_a', {})
        portfolio_b = data.get('portfolio_b', {})
        monthly_sip = float(data.get('monthly_sip', 10000))
        years = int(data.get('years', 5))
        
        if not portfolio_a or not portfolio_b:
            return jsonify({'error': 'Both portfolio_a and portfolio_b are required'}), 400
        
        results = sip_calc.compare_portfolios(portfolio_a, portfolio_b, monthly_sip, years)
        return jsonify(results)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


@app.route('/api/get-ai-insight', methods=['POST'])
def get_ai_insight():
    """Get AI explanation and suggestion based on analysis data"""
    try:
        data = request.get_json()
        context_type = data.get('context', 'general')
        metrics = data.get('metrics', {})
        
        # Construct Prompt based on context
        prompt = ""
        
        # Prepare System Message
        system_msg = "You are a professional financial advisor. Your task is to provide clear, actionable advice in Markdown format. Do NOT output JSON. Do NOT analyze the rhetorical devices. Just give the advice."

        if context_type == 'comparison':
            prompt = f"""
            Analyze this insurance vs investment comparison:

            **UserData:**
            - Term: {metrics.get('years')} years
            - Annual Premium: ₹{metrics.get('annual_outflow')}
            - Endowment Maturity: ₹{metrics.get('endowment_value')}
            - BTIR (Term+Invest) Value: ₹{metrics.get('btir_value')}
            - Endowment Return (IRR): {metrics.get('endowment_irr')}%
            - Market Return Assumed: {metrics.get('return_rate')}%
            - Opportunity Cost: ₹{metrics.get('opportunity_cost')}

            **Your Task:**
            1. **The Verdict:** plainly state which option wins and by how much.
            2. **Inflation Reality:** Explain that {metrics.get('endowment_irr')}% return might not beat inflation (typically 6-7%), meaning purchasing power goes down.
            3. **Recommendation:** Suggest 'Buy Term + Invest Rest' if the math supports it strongly.
            4. **Disclaimer:** "Not financial advice."

            Output strictly in Markdown. bold the key numbers.
            """
            
        elif context_type == 'sip':
            prompt = f"""
            Analyze this SIP Projection:

            **UserData:**
            - Monthly Investment: ₹{metrics.get('monthly_sip')}
            - Duration: {metrics.get('years')} years
            - Expected Return: {metrics.get('return_rate')}%
            - Total Invested: ₹{metrics.get('total_invested')}
            - Final Corpus: ₹{metrics.get('estimated_value')}
            - Wealth Created: ₹{metrics.get('wealth_gained')}

            **Your Task:**
            1. **Wealth Assessment:** Is this a good corpus?
            2. **Power of Compounding:** Highlight that wealth gained (₹{metrics.get('wealth_gained')}) is money working for them.
            3. **Pro Tip:** Suggest a 10% annual "Step-Up" SIP. Estimate how much more they could make (rule of thumb: almost double the corpus in long run).
            4. **Disclaimer.**

            Output as Markdown. Keep it encouraging!
            """

        elif context_type == 'portfolio_compare':
            diff = metrics.get('diff_value')
            winner = metrics.get('winner')
            prompt = f"""
            Compare two portfolios:

            **Winner:** Portfolio {winner} (Wins by ₹{diff})
            
            **Portfolio A:** {metrics.get('portfolio_a_type')} | Return: {metrics.get('portfolio_a_return')}%
            **Portfolio B:** {metrics.get('portfolio_b_type')} | Return: {metrics.get('portfolio_b_return')}%

            **Your Task:**
            1. **Why it won:** Briefly explain (e.g., higher equity allocation usually wins in long term).
            2. **Risk vs Reward:** Higher returns usually mean higher volatility. Mention this trade-off.
            3. **Strategy:** Recommend sticking to the asset allocation that matches their risk appetite.
            4. **Disclaimer.**

            Output as Markdown.
            """

        elif context_type == 'goal':
            prompt = f"""
            Financial Goal Analysis:
            
            **Goal:** Reach ₹{metrics.get('target_amount')} in {metrics.get('years')} years.
            **Required SIP:** ₹{metrics.get('required_sip')} / month.
            **Assumed Return:** {metrics.get('return_rate')}%

            **Your Task:**
            1. **Reality Check:** Is this SIP amount typically manageable?
            2. **Optimization:** Suggest increasing the investment realized return (if conservative) or extending the timeline to lower the burden.
            3. **Disclaimer.**

            Output as Markdown.
            """
        
        else:
            return jsonify({'error': 'Invalid context'}), 400

        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_msg,
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=300,
        )

        explanation = chat_completion.choices[0].message.content
        return jsonify({'insight': explanation})

    except Exception as e:
        print(f"AI API Error: {e}")
        # Fallback response if API fails
        return jsonify({'insight': "**AI Insight Unavailable.**\n\nWe couldn't reach our financial brain at the moment. Please check your API key or internet connection.\n\n_Disclaimer: Standard financial disclaimers apply._"}), 200


@app.route('/sip/compare', methods=['GET', 'POST'])
def sip_compare():
    """Portfolio comparison page"""
    presets = sip_calc.get_presets()
    asset_classes = sip_calc.get_asset_classes()
    
    if request.method == 'POST':
        try:
            monthly_sip = float(request.form.get('monthly_sip', 10000))
            years = int(request.form.get('years', 5))
            
            # Build portfolio A
            portfolio_a = build_portfolio_from_form(request.form, 'a')
            
            # Build portfolio B
            portfolio_b = build_portfolio_from_form(request.form, 'b')
            
            # Run comparison
            results = sip_calc.compare_portfolios(portfolio_a, portfolio_b, monthly_sip, years)
            
            # Create charts
            charts = create_comparison_charts(results)
            
            return render_template('result_sip_compare.html',
                                   results=results,
                                   charts=charts)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template('index.html',
                                   error=f"Error: {str(e)}",
                                   sip_tab=True, presets=presets, asset_classes=asset_classes)
    
    return render_template('index.html', sip_tab=True, compare_mode=True, 
                           presets=presets, asset_classes=asset_classes)


def build_portfolio_from_form(form_data, prefix):
    """Build portfolio configuration from form data"""
    portfolio_type = form_data.get(f'portfolio_{prefix}_type', 'preset')
    
    if portfolio_type == 'preset':
        return {
            'type': 'preset',
            'preset': form_data.get(f'portfolio_{prefix}_preset', 'balanced')
        }
    elif portfolio_type == 'custom':
        allocation = {}
        asset_classes = ['large_cap_equity', 'mid_cap_equity', 'small_cap_equity', 
                         'debt', 'gold', 'international']
        for asset in asset_classes:
            pct = float(form_data.get(f'portfolio_{prefix}_alloc_{asset}', 0))
            if pct > 0:
                allocation[asset] = pct
        return {
            'type': 'custom',
            'allocation': allocation
        }
    elif portfolio_type == 'funds':
        # Parse funds configuration from form
        funds_config = {}
        import json
        funds_json = form_data.get(f'portfolio_{prefix}_funds', '{}')
        try:
            funds_config = json.loads(funds_json)
        except:
            pass
        return {
            'type': 'funds',
            'funds': funds_config
        }
    
    return {'type': 'preset', 'preset': 'balanced'}


def create_comparison_charts(results: dict) -> dict:
    """Create charts for portfolio comparison"""
    charts = {}
    
    portfolio_a = results.get('portfolio_a', {})
    portfolio_b = results.get('portfolio_b', {})
    delta = results.get('delta', {})
    
    # Comparison bar chart
    fig_comparison = go.Figure(data=[
        go.Bar(
            name='Portfolio A',
            x=['Final Value', 'Return %', 'Alpha'],
            y=[
                portfolio_a.get('final_value', 0),
                portfolio_a.get('return_pct', 0),
                portfolio_a.get('alpha', 0)
            ],
            marker_color='#4a90e2',
            text=[
                f"₹{portfolio_a.get('final_value', 0):,.0f}",
                f"{portfolio_a.get('return_pct', 0):.1f}%",
                f"{portfolio_a.get('alpha', 0):.1f}%"
            ],
            textposition='outside'
        ),
        go.Bar(
            name='Portfolio B',
            x=['Final Value', 'Return %', 'Alpha'],
            y=[
                portfolio_b.get('final_value', 0),
                portfolio_b.get('return_pct', 0),
                portfolio_b.get('alpha', 0)
            ],
            marker_color='#51cf66',
            text=[
                f"₹{portfolio_b.get('final_value', 0):,.0f}",
                f"{portfolio_b.get('return_pct', 0):.1f}%",
                f"{portfolio_b.get('alpha', 0):.1f}%"
            ],
            textposition='outside'
        )
    ])
    
    fig_comparison.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#7d7d7d'),
        margin=dict(t=50, b=50, l=50, r=50),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    charts['comparison'] = fig_comparison.to_json()
    
    return charts


if __name__ == '__main__':
    app.run(debug=True)