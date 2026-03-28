import math

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots

from Execution.func_stats import calculate_metrics


def plot_trends(sym_1, sym_2, prices_1, prices_2):
    metrics = calculate_metrics(prices_1, prices_2)
    spread = metrics["spread"]
    zscore = metrics["zscore_list"]

    df = pd.DataFrame(columns=[sym_1, sym_2])
    df[sym_1] = prices_1
    df[sym_2] = prices_2
    df[f"{sym_1}_pct"] = df[sym_1] / prices_1[0]
    df[f"{sym_2}_pct"] = df[sym_2] / prices_2[0]
    series_1 = df[f"{sym_1}_pct"].astype(float).values
    series_2 = df[f"{sym_2}_pct"].astype(float).values

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
        go.Scatter(x=list(range(len(zscore))), y=zscore, mode="lines", name="Z-Score"),
        row=3,
        col=1,
    )
    fig.add_hline(
        y=0,
        line_dash="dash",
        row=3,
        col=1,
        annotation_text="Z-score Threshold",
        annotation_position="bottom right",
    )

    fig.update_layout(
        height=800,
        width=1000,
        title_text=f"Price and Spread - {sym_1} vs {sym_2}",
        showlegend=True,
        xaxis_rangeslider_visible=False,
    )
    fig.show()


def round_quantity(quantity, step_size):
    rounded = math.floor(quantity / step_size) * step_size
    precision = len(str(step_size).split(".")[-1])
    return round(rounded, precision)
