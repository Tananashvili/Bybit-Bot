from config_strategy_api import z_score_window
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


# Put close prices into a list
def extract_close_prices(prices):
    close_prices = []
    for price_values in prices:
        close_price = float(price_values)
        if math.isnan(close_price):
            return []
        close_prices.append(close_price)
    return close_prices


# Calculate cointegrated pairs
def get_cointegrated_pairs(prices, bad_pairs):

    # Loop through coins and check for co-integration
    coint_pair_list = []
    included_list = []
    for sym_1 in prices.keys():

        # Check each coin against the first (sym_1)
        for sym_2 in prices.keys():
            if sym_2 != sym_1:

                # Get unique combination id and ensure one off check
                sorted_characters = sorted(sym_1 + sym_2)
                unique = "".join(sorted_characters)
                if unique in included_list:
                    continue

                # Get close prices
                series_1 = extract_close_prices(prices[sym_1])
                series_2 = extract_close_prices(prices[sym_2])

                # Check for cointegration and add cointegrated pair
                coint_flag, p_value, t_value, c_value, hedge_ratio, zero_crossings = calculate_cointegration(series_1, series_2)
                spread = calculate_spread(series_1, series_2, hedge_ratio)
                zscore = calculate_zscore(spread)
                if coint_flag == 1:
                    included_list.append(unique)
                    coint_pair_list.append({
                        "sym_1": sym_1,
                        "sym_2": sym_2,
                        "p_value": p_value,
                        "t_value": t_value,
                        "c_value": c_value,
                        "hedge_ratio": hedge_ratio,
                        "zero_crossings": zero_crossings,
                        "z_score": zscore[-1],
                        "abs": abs(zscore[-1])
                    })

    # Output results
    df_coint = pd.DataFrame(coint_pair_list)
    df_coint = df_coint[~df_coint['sym_1'].isin(bad_pairs) & ~df_coint['sym_2'].isin(bad_pairs)]
    df_coint = df_coint.sort_values("zero_crossings", ascending=False)
    df_coint.to_excel("2_cointegrated_pairs.xlsx", index=False)

    return df_coint
