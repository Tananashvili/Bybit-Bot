from Strategy.func_cointegration import calculate_cointegration, calculate_spread, calculate_zscore
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots


def plot_trends(sym_1, sym_2, price_data):
    # Extract prices
    prices_1 = price_data[sym_1]
    prices_2 = price_data[sym_2]

    # Get spread and zscore
    coint_flag, p_value, t_value, c_value, hedge_ratio, zero_crossing = calculate_cointegration(prices_1, prices_2)
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

    # Save results for backtesting
    df_2 = pd.DataFrame()
    df_2[sym_1] = prices_1
    df_2[sym_2] = prices_2
    df_2["Spread"] = spread
    df_2["ZScore"] = zscore
    df_2.to_csv("3_backtest_file.csv")
    print("File for backtesting saved.")
    print(zscore[-1])

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
    fig.add_hline(y=2, line_dash="dash", row=3, col=1, annotation_text="Z-score Threshold", annotation_position="bottom right")
    
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


