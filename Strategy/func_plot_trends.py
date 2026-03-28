import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots

from Strategy.func_cointegration import calculate_cointegration, calculate_spread, calculate_zscore


def plot_trends(sym_1, sym_2, price_data):
    prices_1 = price_data[sym_1]
    prices_2 = price_data[sym_2]

    (
        _coint_flag,
        _p_value,
        _t_value,
        _c_value,
        hedge_ratio,
        _zero_crossing,
        intercept,
        _half_life,
    ) = calculate_cointegration(prices_1, prices_2)
    spread = calculate_spread(prices_1, prices_2, hedge_ratio, intercept)
    zscore_data = calculate_zscore(spread)
    zscore_list = zscore_data["z_scores"]

    df = pd.DataFrame(columns=[sym_1, sym_2])
    df[sym_1] = prices_1
    df[sym_2] = prices_2
    df[f"{sym_1}_pct"] = df[sym_1] / prices_1[0]
    df[f"{sym_2}_pct"] = df[sym_2] / prices_2[0]
    series_1 = df[f"{sym_1}_pct"].astype(float).values
    series_2 = df[f"{sym_2}_pct"].astype(float).values

    export_df = pd.DataFrame()
    export_df[sym_1] = prices_1
    export_df[sym_2] = prices_2
    export_df["Spread"] = spread
    export_df["ZScore"] = pd.Series(zscore_list).reindex(range(len(spread)))
    export_df.to_csv("3_backtest_file.csv", index=False)
    print("File for backtesting saved.")
    if zscore_list:
        print(zscore_list[-1])

    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=[
            "Percentage Change in Prices",
            "Spread Between Prices",
            "Z-Score of the Spread",
        ],
    )

    fig.add_trace(
        go.Scatter(x=list(range(len(series_1))), y=series_1, mode="lines", name=f"{sym_1} Percentage Change"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=list(range(len(series_2))), y=series_2, mode="lines", name=f"{sym_2} Percentage Change"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=list(range(len(spread))), y=spread, mode="lines", name="Spread"),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=list(range(len(zscore_list))), y=zscore_list, mode="lines", name="Z-Score"),
        row=3,
        col=1,
    )
    fig.add_hline(y=2, line_dash="dash", row=3, col=1, annotation_text="Z-score Threshold", annotation_position="bottom right")

    fig.update_layout(
        height=800,
        width=1000,
        title_text=f"Price and Spread - {sym_1} vs {sym_2}",
        showlegend=True,
        xaxis_rangeslider_visible=False,
    )

    fig.show()
