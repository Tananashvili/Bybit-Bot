import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from config_execution_api import z_score_window
from statsmodels.tsa.stattools import coint
import statsmodels.api as sm
import pandas as pd
import numpy as np
import math


# Calculate Z-Score
def calculate_zscore(spread):
    df = pd.DataFrame(spread)
    mean = df.rolling(center=False, window=z_score_window).mean()
    std = df.rolling(center=False, window=z_score_window).std()
    x = df.rolling(center=False, window=1).mean()
    df["ZSCORE"] = (x - mean) / std
    return df["ZSCORE"].astype(float).values


# Calculate spread
def calculate_spread(series_1, series_2, hedge_ratio):
    spread = pd.Series(series_1) - (pd.Series(series_2) * hedge_ratio)
    return spread


# Calculate co-integration
def calculate_cointegration(series_1, series_2):
    coint_flag = 0
    try:
        coint_res = coint(series_1, series_2)
        t_value = coint_res[0]
        p_value = coint_res[1]
        critical_value = coint_res[2][1]
        model = sm.OLS(series_1, series_2).fit()
        hedge_ratio = model.params[0]
        spread = calculate_spread(series_1, series_2, hedge_ratio)
        zero_crossings = len(np.where(np.diff(np.sign(spread)))[0])
        if p_value < 0.01 and t_value < critical_value:
            coint_flag = 1
    except ValueError:
        print('Invalid input, x is constant')
        coint_flag = p_value = t_value = critical_value = hedge_ratio = zero_crossings = 0

    return (coint_flag, round(p_value, 2), round(t_value, 2), round(critical_value, 2), round(hedge_ratio, 2), zero_crossings)


def plot_trends(sym_1, sym_2, prices_1, prices_2):

    # Get spread and zscore
    _, _, _, _, hedge_ratio, _ = calculate_cointegration(prices_1, prices_2)
    spread = calculate_spread(prices_1, prices_2, hedge_ratio)
    zscore = calculate_zscore(spread)

    # Calculate percentage changes
    df = pd.DataFrame(columns=[sym_1, sym_2])
    df[sym_1] = prices_1
    df[sym_2] = prices_2
    df[f"{sym_1}_pct"] = df[sym_1] / prices_1[0]
    df[f"{sym_2}_pct"] = df[sym_2] / prices_2[0]
    series_1 = df[f"{sym_1}_pct"].astype(float).values
    series_2 = df[f"{sym_2}_pct"].astype(float).values

    # Create subplots
    fig = make_subplots(rows=3, cols=1, subplot_titles=[
        'Percentage Change in Prices',
        'Spread Between Prices',
        'Z-Score of the Spread'
    ])

    # Add Percentage Change plot
    fig.add_trace(go.Scatter(x=list(range(len(series_1))), y=series_1, mode='lines', name=f'{sym_1} Percentage Change'), row=1, col=1)
    fig.add_trace(go.Scatter(x=list(range(len(series_2))), y=series_2, mode='lines', name=f'{sym_2} Percentage Change'), row=1, col=1)

    # Add Spread plot
    fig.add_trace(go.Scatter(x=list(range(len(spread))), y=spread, mode='lines', name='Spread'), row=2, col=1)

    # Add Z-Score plot
    fig.add_trace(go.Scatter(x=list(range(len(zscore))), y=zscore, mode='lines', name='Z-Score'), row=3, col=1)

    # Add a horizontal line for Z-Score threshold (e.g., Z-score of 2)
    fig.add_hline(y=0, line_dash="dash", row=3, col=1, annotation_text="Z-score Threshold", annotation_position="bottom right")
    
    # Update layout
    fig.update_layout(
        height=800, 
        width=1000, 
        title_text=f"Price and Spread - {sym_1} vs {sym_2}", 
        showlegend=True,
        xaxis_rangeslider_visible=False  # Disable the extra rangeslider at the bottom
    )

    # Show interactive plot
    fig.show()


def filter_data():
    #and abs(zscore[-1]) > 2 and zero_crossings > 25
    pass