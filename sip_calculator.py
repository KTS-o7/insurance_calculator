"""
SIP Calculator Module

Provides SIP simulation, allocation backtesting, and alpha calculation
using data from MFapi.in, mf.captnemo.in, and yfinance.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from scipy import optimize
from functools import lru_cache
import yfinance as yf
from typing import Dict, List, Tuple, Optional
import json


# =============================================================================
# DATA FETCHERS
# =============================================================================

class MFDataFetcher:
    """Fetch mutual fund data from MFapi.in"""
    
    BASE_URL = "https://api.mfapi.in"
    
    @lru_cache(maxsize=100)
    def search_schemes(self, query: str) -> List[Dict]:
        """Search mutual fund schemes by name"""
        try:
            response = requests.get(f"{self.BASE_URL}/mf/search?q={query}", timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error searching schemes: {e}")
            return []
    
    def get_scheme_nav_history(self, scheme_code: str) -> pd.DataFrame:
        """Get NAV history for a scheme"""
        try:
            response = requests.get(f"{self.BASE_URL}/mf/{scheme_code}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                nav_data = data.get('data', [])
                if nav_data:
                    df = pd.DataFrame(nav_data)
                    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
                    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
                    df = df.dropna()
                    df = df.sort_values('date').reset_index(drop=True)
                    return df
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching NAV history: {e}")
            return pd.DataFrame()


class CaptnemoDataFetcher:
    """Fetch rich fund metadata from mf.captnemo.in"""
    
    BASE_URL = "https://mf.captnemo.in"
    
    def get_fund_details(self, isin: str) -> Dict:
        """Get detailed fund metadata by ISIN"""
        try:
            response = requests.get(f"{self.BASE_URL}/kuvera/{isin}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    fund = data[0]
                    return {
                        'name': fund.get('name', ''),
                        'short_name': fund.get('short_name', ''),
                        'category': fund.get('category', ''),
                        'fund_type': fund.get('fund_type', ''),
                        'fund_house': fund.get('fund_name', ''),
                        'crisil_rating': fund.get('crisil_rating', ''),
                        'expense_ratio': fund.get('expense_ratio', ''),
                        'fund_rating': fund.get('fund_rating', 0),
                        'volatility': fund.get('volatility', 0),
                        'aum': fund.get('aum', 0),
                        'returns': fund.get('returns', {}),
                        'fund_manager': fund.get('fund_manager', ''),
                        'start_date': fund.get('start_date', '')
                    }
            return {}
        except Exception as e:
            print(f"Error fetching fund details: {e}")
            return {}
    
    def get_nav_history(self, isin: str) -> pd.DataFrame:
        """Get NAV history by ISIN"""
        try:
            response = requests.get(f"{self.BASE_URL}/nav/{isin}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                historical = data.get('historical_nav', [])
                if historical:
                    df = pd.DataFrame(historical, columns=['date', 'nav'])
                    df['date'] = pd.to_datetime(df['date'])
                    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
                    df = df.dropna().sort_values('date').reset_index(drop=True)
                    return df
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching NAV history from Captnemo: {e}")
            return pd.DataFrame()


class ETFDataFetcher:
    """Fetch ETF prices and index data from yfinance"""
    
    # Common Indian ETF tickers
    TICKERS = {
        'nifty50': '^NSEI',
        'nifty_etf': 'NIFTYBEES.NS',
        'nifty_next50': 'JUNIORBEES.NS',
        'gold_etf': 'GOLDBEES.NS',
        'bank_nifty': 'BANKBEES.NS'
    }
    
    def get_history(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Get historical price data for a ticker"""
        try:
            data = yf.download(
                ticker, 
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False
            )
            if not data.empty:
                df = data[['Close']].reset_index()
                df.columns = ['date', 'nav']
                df['date'] = pd.to_datetime(df['date'])
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching ETF data: {e}")
            return pd.DataFrame()
    
    def get_nifty50_history(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Get Nifty 50 index history"""
        return self.get_history(self.TICKERS['nifty50'], start_date, end_date)
    
    def get_etf_history(self, etf_name: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Get ETF history by common name"""
        ticker = self.TICKERS.get(etf_name, etf_name)
        return self.get_history(ticker, start_date, end_date)


# =============================================================================
# SIP SIMULATOR
# =============================================================================

class SIPSimulator:
    """Simulate SIP investments and calculate returns"""
    
    def simulate_sip(
        self, 
        nav_data: pd.DataFrame, 
        monthly_amount: float,
        start_date: date,
        end_date: date,
        sip_day: int = 1
    ) -> Dict:
        """
        Simulate monthly SIP investments
        
        Returns dict with:
        - total_invested: Total amount invested
        - final_value: Current portfolio value
        - total_units: Total units accumulated
        - transactions: List of all SIP transactions
        - portfolio_series: Time series of portfolio value
        """
        if nav_data.empty:
            return {
                'total_invested': 0,
                'final_value': 0,
                'total_units': 0,
                'absolute_return': 0,
                'return_pct': 0,
                'transactions': [],
                'portfolio_series': pd.DataFrame()
            }
        
        # Filter NAV data to date range
        nav_data = nav_data[
            (nav_data['date'].dt.date >= start_date) & 
            (nav_data['date'].dt.date <= end_date)
        ].copy()
        
        if nav_data.empty:
            return {
                'total_invested': 0,
                'final_value': 0,
                'total_units': 0,
                'absolute_return': 0,
                'return_pct': 0,
                'transactions': [],
                'portfolio_series': pd.DataFrame()
            }
        
        transactions = []
        total_units = 0
        total_invested = 0
        
        # Generate SIP dates
        current = date(start_date.year, start_date.month, min(sip_day, 28))
        if current < start_date:
            if current.month == 12:
                current = date(current.year + 1, 1, min(sip_day, 28))
            else:
                current = date(current.year, current.month + 1, min(sip_day, 28))
        
        while current <= end_date:
            # Find NAV on or after SIP date
            nav_on_date = nav_data[nav_data['date'].dt.date >= current]
            if not nav_on_date.empty:
                nav_row = nav_on_date.iloc[0]
                nav = nav_row['nav']
                actual_date = nav_row['date'].date()
                
                units = monthly_amount / nav
                total_units += units
                total_invested += monthly_amount
                
                transactions.append({
                    'date': actual_date,
                    'amount': monthly_amount,
                    'nav': nav,
                    'units': units,
                    'cumulative_units': total_units,
                    'cumulative_invested': total_invested
                })
            
            # Next month
            if current.month == 12:
                current = date(current.year + 1, 1, min(sip_day, 28))
            else:
                current = date(current.year, current.month + 1, min(sip_day, 28))
        
        # Calculate final value
        final_nav = nav_data.iloc[-1]['nav'] if not nav_data.empty else 0
        final_value = total_units * final_nav
        
        # Build portfolio time series
        portfolio_series = self._build_portfolio_series(nav_data, transactions)
        
        absolute_return = final_value - total_invested
        return_pct = (absolute_return / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'total_invested': round(total_invested, 2),
            'final_value': round(final_value, 2),
            'total_units': round(total_units, 4),
            'absolute_return': round(absolute_return, 2),
            'return_pct': round(return_pct, 2),
            'transactions': transactions,
            'portfolio_series': portfolio_series
        }
    
    def _build_portfolio_series(
        self, 
        nav_data: pd.DataFrame, 
        transactions: List[Dict]
    ) -> pd.DataFrame:
        """Build daily portfolio value time series"""
        if not transactions or nav_data.empty:
            return pd.DataFrame()
        
        result = []
        tx_idx = 0
        cumulative_units = 0
        cumulative_invested = 0
        
        for _, row in nav_data.iterrows():
            nav_date = row['date'].date()
            nav = row['nav']
            
            # Update units if SIP happened on or before this date
            while tx_idx < len(transactions) and transactions[tx_idx]['date'] <= nav_date:
                cumulative_units = transactions[tx_idx]['cumulative_units']
                cumulative_invested = transactions[tx_idx]['cumulative_invested']
                tx_idx += 1
            
            portfolio_value = cumulative_units * nav
            
            result.append({
                'date': nav_date,
                'invested': cumulative_invested,
                'value': portfolio_value,
                'nav': nav
            })
        
        return pd.DataFrame(result)
    
    def calculate_xirr(self, transactions: List[Dict], final_value: float, end_date: date) -> float:
        """Calculate XIRR (Extended IRR) for the investment"""
        if not transactions or final_value <= 0:
            return 0.0
        
        # Build cashflows: negative for investments, positive for final value
        cashflows = []
        dates = []
        
        for tx in transactions:
            cashflows.append(-tx['amount'])
            dates.append(tx['date'])
        
        # Add final value as positive cashflow
        cashflows.append(final_value)
        dates.append(end_date)
        
        return self._xirr(dates, cashflows)
    
    def _xirr(self, dates: List[date], cashflows: List[float]) -> float:
        """Calculate XIRR using Newton-Raphson method"""
        if len(dates) < 2:
            return 0.0
        
        # Convert dates to year fractions from first date
        first_date = dates[0]
        year_fracs = [(d - first_date).days / 365.0 for d in dates]
        
        def npv(rate):
            return sum(cf / ((1 + rate) ** yf) for cf, yf in zip(cashflows, year_fracs))
        
        def npv_derivative(rate):
            return sum(-yf * cf / ((1 + rate) ** (yf + 1)) for cf, yf in zip(cashflows, year_fracs))
        
        # Newton-Raphson iteration
        try:
            rate = 0.1  # Initial guess
            for _ in range(100):
                npv_val = npv(rate)
                if abs(npv_val) < 1e-6:
                    break
                deriv = npv_derivative(rate)
                if abs(deriv) < 1e-10:
                    break
                rate = rate - npv_val / deriv
                if rate <= -1:
                    rate = -0.99
            return round(rate * 100, 2)  # Return as percentage
        except:
            return 0.0
    
    def calculate_cagr(self, start_value: float, end_value: float, years: float) -> float:
        """Calculate Compound Annual Growth Rate"""
        if start_value <= 0 or end_value <= 0 or years <= 0:
            return 0.0
        cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
        return round(cagr, 2)


# =============================================================================
# ALPHA CALCULATOR
# =============================================================================

class AlphaCalculator:
    """Compare portfolio returns against benchmark"""
    
    def calculate_alpha(self, portfolio_return: float, benchmark_return: float) -> float:
        """Calculate simple alpha (excess return)"""
        return round(portfolio_return - benchmark_return, 2)
    
    def generate_comparison_data(
        self, 
        portfolio_series: pd.DataFrame,
        benchmark_data: pd.DataFrame
    ) -> Dict:
        """Generate portfolio vs benchmark comparison data"""
        if portfolio_series.empty or benchmark_data.empty:
            return {'dates': [], 'portfolio': [], 'benchmark': [], 'alpha': []}
        
        # Merge on date
        portfolio_series['date'] = pd.to_datetime(portfolio_series['date'])
        benchmark_data['date'] = pd.to_datetime(benchmark_data['date'])
        
        merged = pd.merge(
            portfolio_series[['date', 'value', 'invested']],
            benchmark_data[['date', 'nav']],
            on='date',
            how='inner'
        )
        
        if merged.empty:
            return {'dates': [], 'portfolio': [], 'benchmark': [], 'alpha': []}
        
        # Normalize both to base 100
        first_value = merged['value'].iloc[0] if merged['value'].iloc[0] > 0 else 1
        first_benchmark = merged['nav'].iloc[0] if merged['nav'].iloc[0] > 0 else 1
        
        # For portfolio, we normalize invested amount to 100 and show relative growth
        merged['portfolio_normalized'] = (merged['value'] / merged['invested']) * 100
        merged['benchmark_normalized'] = (merged['nav'] / first_benchmark) * 100
        merged['alpha_daily'] = merged['portfolio_normalized'] - merged['benchmark_normalized']
        
        return {
            'dates': merged['date'].dt.strftime('%Y-%m-%d').tolist(),
            'portfolio': merged['portfolio_normalized'].round(2).tolist(),
            'benchmark': merged['benchmark_normalized'].round(2).tolist(),
            'alpha': merged['alpha_daily'].round(2).tolist(),
            'invested': merged['invested'].round(2).tolist(),
            'value': merged['value'].round(2).tolist()
        }
    
    def calculate_rolling_returns(
        self, 
        nav_data: pd.DataFrame, 
        periods: List[int] = [252, 756, 1260]  # 1Y, 3Y, 5Y in trading days
    ) -> Dict:
        """Calculate rolling returns for different periods"""
        results = {}
        for period in periods:
            if len(nav_data) >= period:
                nav_data[f'return_{period}'] = (
                    nav_data['nav'].pct_change(period) * 100
                )
                results[period] = nav_data[f'return_{period}'].iloc[-1]
        return results


# =============================================================================
# ALLOCATION ANALYZER
# =============================================================================

class AllocationAnalyzer:
    """Backtest asset allocation strategies with presets and custom allocations"""
    
    ASSET_CLASSES = {
        'large_cap_equity': {
            'label': 'Large Cap Equity',
            'proxy_ticker': 'NIFTYBEES.NS',
            'color': '#4a90e2'
        },
        'mid_cap_equity': {
            'label': 'Mid Cap Equity', 
            'proxy_ticker': 'JUNIORBEES.NS',
            'color': '#7c3aed'
        },
        'small_cap_equity': {
            'label': 'Small Cap Equity',
            'proxy_ticker': None,  # Use MF scheme
            'proxy_mf_code': '120505',  # Example small cap fund
            'color': '#ec4899'
        },
        'debt': {
            'label': 'Debt/Bonds',
            'proxy_ticker': None,
            'proxy_mf_code': '119551',  # Example liquid fund  
            'color': '#10b981'
        },
        'gold': {
            'label': 'Gold',
            'proxy_ticker': 'GOLDBEES.NS',
            'color': '#f59e0b'
        },
        'international': {
            'label': 'International Equity',
            'proxy_ticker': None,
            'proxy_mf_code': '120503',  # Example international fund
            'color': '#06b6d4'
        }
    }
    
    PRESETS = {
        'conservative': {
            'label': 'Conservative',
            'description': 'Low risk, stable returns',
            'allocation': {
                'large_cap_equity': 30,
                'debt': 50,
                'gold': 20
            }
        },
        'balanced': {
            'label': 'Balanced',
            'description': 'Moderate risk and growth',
            'allocation': {
                'large_cap_equity': 50,
                'mid_cap_equity': 10,
                'debt': 30,
                'gold': 10
            }
        },
        'growth': {
            'label': 'Growth',
            'description': 'Higher risk, higher returns',
            'allocation': {
                'large_cap_equity': 60,
                'mid_cap_equity': 20,
                'small_cap_equity': 10,
                'gold': 10
            }
        },
        'aggressive': {
            'label': 'Aggressive',
            'description': 'Maximum growth potential',
            'allocation': {
                'large_cap_equity': 50,
                'mid_cap_equity': 30,
                'small_cap_equity': 15,
                'gold': 5
            }
        }
    }
    
    def __init__(self):
        self.etf_fetcher = ETFDataFetcher()
        self.mf_fetcher = MFDataFetcher()
        self.sip_simulator = SIPSimulator()
        self.alpha_calculator = AlphaCalculator()
    
    def get_asset_nav_data(
        self, 
        asset_class: str, 
        start_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """Get NAV data for an asset class using its proxy"""
        asset_info = self.ASSET_CLASSES.get(asset_class, {})
        
        if asset_info.get('proxy_ticker'):
            return self.etf_fetcher.get_history(
                asset_info['proxy_ticker'], 
                start_date, 
                end_date
            )
        elif asset_info.get('proxy_mf_code'):
            return self.mf_fetcher.get_scheme_nav_history(
                asset_info['proxy_mf_code']
            )
        return pd.DataFrame()
    
    def backtest_allocation(
        self,
        allocation: Dict[str, float],
        monthly_sip: float,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Backtest an allocation strategy
        
        Args:
            allocation: Dict of asset_class -> percentage (must sum to 100)
            monthly_sip: Monthly SIP amount
            start_date: Start date
            end_date: End date
        
        Returns:
            Dict with total results and per-asset breakdowns
        """
        # Validate allocation sums to 100
        total_alloc = sum(allocation.values())
        if abs(total_alloc - 100) > 0.01:
            raise ValueError(f"Allocation must sum to 100%, got {total_alloc}%")
        
        results_by_asset = {}
        total_invested = 0
        total_final_value = 0
        all_transactions = []
        
        # Simulate SIP for each asset class
        for asset_class, percentage in allocation.items():
            if percentage <= 0:
                continue
            
            asset_sip = monthly_sip * (percentage / 100)
            nav_data = self.get_asset_nav_data(asset_class, start_date, end_date)
            
            if nav_data.empty:
                continue
            
            result = self.sip_simulator.simulate_sip(
                nav_data, 
                asset_sip, 
                start_date, 
                end_date
            )
            
            results_by_asset[asset_class] = {
                'percentage': percentage,
                'monthly_sip': asset_sip,
                'invested': result['total_invested'],
                'final_value': result['final_value'],
                'return_pct': result['return_pct'],
                'label': self.ASSET_CLASSES[asset_class]['label'],
                'color': self.ASSET_CLASSES[asset_class]['color']
            }
            
            total_invested += result['total_invested']
            total_final_value += result['final_value']
        
        # Calculate overall returns
        absolute_return = total_final_value - total_invested
        return_pct = (absolute_return / total_invested * 100) if total_invested > 0 else 0
        
        # Get benchmark data and calculate alpha
        benchmark_data = self.etf_fetcher.get_nifty50_history(start_date, end_date)
        benchmark_result = self.sip_simulator.simulate_sip(
            benchmark_data, monthly_sip, start_date, end_date
        )
        
        benchmark_return_pct = benchmark_result.get('return_pct', 0)
        alpha = self.alpha_calculator.calculate_alpha(return_pct, benchmark_return_pct)
        
        # Calculate investment duration
        days = (end_date - start_date).days
        years = days / 365.0
        
        # Calculate XIRR (simplified for combined portfolio)
        xirr = self.sip_simulator.calculate_cagr(total_invested, total_final_value, years)
        
        return {
            'total_invested': round(total_invested, 2),
            'final_value': round(total_final_value, 2),
            'absolute_return': round(absolute_return, 2),
            'return_pct': round(return_pct, 2),
            'xirr': xirr,
            'alpha': alpha,
            'benchmark_return': benchmark_result.get('return_pct', 0),
            'years': round(years, 1),
            'allocation_results': results_by_asset,
            'allocation': allocation
        }
    
    def get_presets(self) -> Dict:
        """Get all allocation presets"""
        return self.PRESETS
    
    def get_asset_classes(self) -> Dict:
        """Get all available asset classes"""
        return {k: {'label': v['label'], 'color': v['color']} 
                for k, v in self.ASSET_CLASSES.items()}


# =============================================================================
# FUND-BASED ANALYZER
# =============================================================================

class FundBasedAnalyzer:
    """Analyze SIP investments using specific mutual fund schemes"""
    
    def __init__(self):
        self.mf_fetcher = MFDataFetcher()
        self.captnemo_fetcher = CaptnemoDataFetcher()
        self.etf_fetcher = ETFDataFetcher()
        self.sip_simulator = SIPSimulator()
        self.alpha_calculator = AlphaCalculator()
    
    def analyze_funds(
        self,
        funds_config: Dict[str, List[Dict]],
        monthly_sip: float,
        years: int = 5,
        end_date: date = None
    ) -> Dict:
        """
        Analyze SIP with specific mutual funds
        
        Args:
            funds_config: Dict mapping asset class to list of funds
                {
                    "large_cap_equity": [
                        {"scheme_code": "120503", "name": "HDFC...", "percentage": 50},
                        {"scheme_code": "100123", "name": "ICICI...", "percentage": 50}
                    ],
                    ...
                }
            monthly_sip: Total monthly SIP amount
            years: Backtest period in years
            end_date: End date (defaults to today)
        
        Returns:
            Analysis results with per-fund breakdown
        """
        if end_date is None:
            end_date = date.today()
        
        start_date = end_date - timedelta(days=int(years * 365))
        
        print(f"DEBUG analyze_funds: start_date={start_date}, end_date={end_date}, years={years}")
        print(f"DEBUG analyze_funds: funds_config={funds_config}")
        
        results_by_asset = {}
        results_by_fund = {}
        total_invested = 0
        total_final_value = 0
        
        # Asset class colors for display
        asset_colors = {
            'large_cap_equity': '#4a90e2',
            'mid_cap_equity': '#7c3aed',
            'small_cap_equity': '#ec4899',
            'debt': '#10b981',
            'gold': '#f59e0b',
            'international': '#06b6d4'
        }
        
        asset_labels = {
            'large_cap_equity': 'Large Cap Equity',
            'mid_cap_equity': 'Mid Cap Equity',
            'small_cap_equity': 'Small Cap Equity',
            'debt': 'Debt/Bonds',
            'gold': 'Gold',
            'international': 'International Equity'
        }
        
        for asset_class, funds in funds_config.items():
            if not funds:
                continue
            
            # Calculate total percentage for this asset class
            asset_total_pct = sum(f.get('percentage', 0) for f in funds)
            asset_monthly_sip = monthly_sip * (asset_total_pct / 100)
            
            asset_results = {
                'label': asset_labels.get(asset_class, asset_class),
                'color': asset_colors.get(asset_class, '#666'),
                'funds': [],
                'total_invested': 0,
                'total_final_value': 0,
                'return_pct': 0,
                'percentage': asset_total_pct,
                'monthly_sip': asset_monthly_sip,
                'invested': 0,
                'final_value': 0
            }
            
            # Calculate total percentage for this asset class
            asset_total_pct = sum(f.get('percentage', 0) for f in funds)
            
            for fund in funds:
                scheme_code = fund.get('scheme_code')
                fund_name = fund.get('name', f'Fund {scheme_code}')
                fund_pct = fund.get('percentage', 0)
                
                if not scheme_code or fund_pct <= 0:
                    continue
                
                # Calculate this fund's portion of total SIP
                fund_sip = monthly_sip * (fund_pct / 100)
                
                # Fetch NAV data
                nav_data = self.mf_fetcher.get_scheme_nav_history(scheme_code)
                
                print(f"DEBUG: Fund {scheme_code} - Raw NAV data rows: {len(nav_data)}")
                
                if nav_data.empty:
                    print(f"DEBUG: Fund {scheme_code} - NAV data is EMPTY after fetch")
                    continue
                
                print(f"DEBUG: Fund {scheme_code} - Date range: {nav_data['date'].min()} to {nav_data['date'].max()}")
                
                # Filter to date range
                nav_data = nav_data[
                    (nav_data['date'].dt.date >= start_date) &
                    (nav_data['date'].dt.date <= end_date)
                ].copy()
                
                print(f"DEBUG: Fund {scheme_code} - After filter: {len(nav_data)} rows")
                
                if nav_data.empty:
                    print(f"DEBUG: Fund {scheme_code} - NAV data is EMPTY after filtering")
                    continue
                
                # Simulate SIP
                result = self.sip_simulator.simulate_sip(
                    nav_data,
                    fund_sip,
                    start_date,
                    end_date
                )
                
                print(f"DEBUG: Fund {scheme_code} - SIP result: invested={result['total_invested']}, final={result['final_value']}")
                
                fund_result = {
                    'scheme_code': scheme_code,
                    'name': fund_name,
                    'percentage': fund_pct,
                    'monthly_sip': fund_sip,
                    'invested': result['total_invested'],
                    'final_value': result['final_value'],
                    'return_pct': result['return_pct'],
                    'absolute_return': result['absolute_return']
                }
                
                asset_results['funds'].append(fund_result)
                asset_results['total_invested'] += result['total_invested']
                asset_results['total_final_value'] += result['final_value']
                asset_results['invested'] += result['total_invested']
                asset_results['final_value'] += result['final_value']
                
                total_invested += result['total_invested']
                total_final_value += result['final_value']
                
                results_by_fund[scheme_code] = fund_result
            
            # Calculate asset class returns
            if asset_results['total_invested'] > 0:
                asset_results['return_pct'] = round(
                    (asset_results['total_final_value'] - asset_results['total_invested']) 
                    / asset_results['total_invested'] * 100, 2
                )
            
            results_by_asset[asset_class] = asset_results
        
        # Overall returns
        absolute_return = total_final_value - total_invested
        return_pct = (absolute_return / total_invested * 100) if total_invested > 0 else 0
        
        # Get benchmark data
        benchmark_data = self.etf_fetcher.get_nifty50_history(start_date, end_date)
        benchmark_result = self.sip_simulator.simulate_sip(
            benchmark_data, monthly_sip, start_date, end_date
        )
        benchmark_return_pct = benchmark_result.get('return_pct', 0)
        alpha = self.alpha_calculator.calculate_alpha(return_pct, benchmark_return_pct)
        
        # Calculate years and CAGR
        days = (end_date - start_date).days
        years_actual = days / 365.0
        xirr = self.sip_simulator.calculate_cagr(total_invested, total_final_value, years_actual)
        
        return {
            'total_invested': round(total_invested, 2),
            'final_value': round(total_final_value, 2),
            'absolute_return': round(absolute_return, 2),
            'return_pct': round(return_pct, 2),
            'xirr': xirr,
            'alpha': alpha,
            'benchmark_return': benchmark_return_pct,
            'years': round(years_actual, 1),
            'allocation_results': results_by_asset,
            'fund_results': results_by_fund,
            'funds_config': funds_config,
            'monthly_sip': monthly_sip,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'mode': 'funds'
        }


# =============================================================================
# PORTFOLIO COMPARATOR
# =============================================================================

class PortfolioComparator:
    """Compare two portfolio configurations side by side"""
    
    def __init__(self):
        self.allocation_analyzer = AllocationAnalyzer()
        self.fund_analyzer = FundBasedAnalyzer()
    
    def compare(
        self,
        portfolio_a: Dict,
        portfolio_b: Dict,
        monthly_sip: float,
        years: int = 5,
        end_date: date = None
    ) -> Dict:
        """
        Compare two portfolios
        
        Args:
            portfolio_a: Portfolio A config with 'type' ('preset', 'custom', 'funds')
                and corresponding data
            portfolio_b: Portfolio B config
            monthly_sip: Monthly SIP amount
            years: Backtest period
            end_date: End date
        
        Returns:
            Comparison results with delta metrics
        """
        if end_date is None:
            end_date = date.today()
        
        start_date = end_date - timedelta(days=int(years * 365))
        
        # Analyze both portfolios
        result_a = self._analyze_portfolio(portfolio_a, monthly_sip, start_date, end_date)
        result_b = self._analyze_portfolio(portfolio_b, monthly_sip, start_date, end_date)
        
        # Calculate deltas
        delta = {
            'final_value_diff': round(result_a.get('final_value', 0) - result_b.get('final_value', 0), 2),
            'return_pct_diff': round(result_a.get('return_pct', 0) - result_b.get('return_pct', 0), 2),
            'alpha_diff': round(result_a.get('alpha', 0) - result_b.get('alpha', 0), 2),
            'xirr_diff': round(result_a.get('xirr', 0) - result_b.get('xirr', 0), 2),
            'winner': 'A' if result_a.get('final_value', 0) > result_b.get('final_value', 0) else 'B'
        }
        
        return {
            'portfolio_a': result_a,
            'portfolio_b': result_b,
            'delta': delta,
            'monthly_sip': monthly_sip,
            'years': years,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
    
    def _analyze_portfolio(
        self,
        portfolio: Dict,
        monthly_sip: float,
        start_date: date,
        end_date: date
    ) -> Dict:
        """Analyze a single portfolio based on its type"""
        portfolio_type = portfolio.get('type', 'preset')
        
        if portfolio_type == 'preset':
            preset_name = portfolio.get('preset', 'balanced')
            presets = self.allocation_analyzer.get_presets()
            allocation = presets.get(preset_name, presets['balanced'])['allocation']
            
            result = self.allocation_analyzer.backtest_allocation(
                allocation, monthly_sip, start_date, end_date
            )
            result['portfolio_type'] = 'preset'
            result['preset_name'] = preset_name
            return result
        
        elif portfolio_type == 'custom':
            allocation = portfolio.get('allocation', {})
            result = self.allocation_analyzer.backtest_allocation(
                allocation, monthly_sip, start_date, end_date
            )
            result['portfolio_type'] = 'custom'
            return result
        
        elif portfolio_type == 'funds':
            funds_config = portfolio.get('funds', {})
            result = self.fund_analyzer.analyze_funds(
                funds_config, monthly_sip,
                years=int((end_date - start_date).days / 365),
                end_date=end_date
            )
            result['portfolio_type'] = 'funds'
            return result
        
        return {}


# =============================================================================
# MAIN SIP CALCULATOR CLASS
# =============================================================================

class SIPCalculator:
    """Main class for SIP calculations - combines all functionality"""
    
    def __init__(self):
        self.mf_fetcher = MFDataFetcher()
        self.captnemo_fetcher = CaptnemoDataFetcher()
        self.etf_fetcher = ETFDataFetcher()
        self.sip_simulator = SIPSimulator()
        self.alpha_calculator = AlphaCalculator()
        self.allocation_analyzer = AllocationAnalyzer()
        self.fund_analyzer = FundBasedAnalyzer()
        self.portfolio_comparator = PortfolioComparator()
    
    def analyze_allocation(
        self,
        allocation: Dict[str, float],
        monthly_sip: float,
        years: int = 5,
        end_date: date = None
    ) -> Dict:
        """
        Main entry point for allocation analysis (asset class mode)
        
        Args:
            allocation: Dict mapping asset class to percentage
            monthly_sip: Monthly SIP amount in INR
            years: Number of years to backtest
            end_date: End date (defaults to today)
        
        Returns:
            Complete analysis results including charts data
        """
        if end_date is None:
            end_date = date.today()
        
        start_date = end_date - timedelta(days=int(years * 365))
        
        # Run backtest
        results = self.allocation_analyzer.backtest_allocation(
            allocation,
            monthly_sip,
            start_date,
            end_date
        )
        
        # Add chart-ready data
        results['start_date'] = start_date.isoformat()
        results['end_date'] = end_date.isoformat()
        results['monthly_sip'] = monthly_sip
        results['mode'] = 'allocation'
        
        return results
    
    def analyze_funds(
        self,
        funds_config: Dict[str, List[Dict]],
        monthly_sip: float,
        years: int = 5,
        end_date: date = None
    ) -> Dict:
        """
        Analyze SIP with specific mutual funds
        
        Args:
            funds_config: Dict mapping asset class to list of funds
            monthly_sip: Monthly SIP amount in INR
            years: Number of years to backtest
            end_date: End date (defaults to today)
        
        Returns:
            Complete analysis results with fund-level breakdown
        """
        return self.fund_analyzer.analyze_funds(
            funds_config, monthly_sip, years, end_date
        )
    
    def compare_portfolios(
        self,
        portfolio_a: Dict,
        portfolio_b: Dict,
        monthly_sip: float,
        years: int = 5,
        end_date: date = None
    ) -> Dict:
        """
        Compare two portfolio configurations
        
        Args:
            portfolio_a: Portfolio A configuration
            portfolio_b: Portfolio B configuration
            monthly_sip: Monthly SIP amount
            years: Backtest period
            end_date: End date
        
        Returns:
            Comparison results with delta metrics
        """
        return self.portfolio_comparator.compare(
            portfolio_a, portfolio_b, monthly_sip, years, end_date
        )
    
    def get_presets(self) -> Dict:
        """Get allocation presets"""
        return self.allocation_analyzer.get_presets()
    
    def get_asset_classes(self) -> Dict:
        """Get available asset classes"""
        return self.allocation_analyzer.get_asset_classes()
    
    def search_schemes(self, query: str) -> List[Dict]:
        """Search mutual fund schemes"""
        return self.mf_fetcher.search_schemes(query)
    
    def get_fund_details(self, isin: str) -> Dict:
        """Get fund details from Captnemo"""
        return self.captnemo_fetcher.get_fund_details(isin)
