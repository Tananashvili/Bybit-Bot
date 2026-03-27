from Strategy.config_strategy_api import z_score_window
from statsmodels.tsa.stattools import coint
import statsmodels.api as sm
import pandas as pd
import numpy as np
import math


# Calculate Z-Score
def calculate_zscore(spread):
     # Convert spread to DataFrame
    df = pd.DataFrame(spread, columns=["Values"])
    
    # Calculate rolling mean and std
    mean = df["Values"].rolling(window=z_score_window, center=False).mean()
    std = df["Values"].rolling(window=z_score_window, center=False).std()
    x = df["Values"]
    
    # Calculate Z-Score
    df["ZSCORE"] = (x - mean) / std
    
    # Convert Z-Score column to numpy array
    z_scores = df["ZSCORE"].dropna().astype(float).values
    
    # Calculate min and max of Z-Scores
    z_min = z_scores.min()
    z_max = z_scores.max()

    min_treshold = z_min * 0.1
    max_treshold = z_max * 0.1
    
    # Count occurrences of values close to min or max
    close_to_min = -1
    close_to_max = -1

    for i in z_scores:
        if i >= z_max - max_treshold:
            close_to_max += 1
        if i <= z_min - min_treshold:
            close_to_min += 1
    
    return {"z_scores": z_scores, "z_min": z_min, "z_max": z_max, "close_to_min_count": close_to_min, "close_to_max_count": close_to_max}



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

    return (coint_flag, round(p_value, 2), round(t_value, 2), round(critical_value, 2), hedge_ratio, zero_crossings)


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
                zscore_data = calculate_zscore(spread)
                zscore_list = zscore_data["z_scores"]

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
                        "z_score": zscore_list[-1],
                        "abs": abs(zscore_list[-1])
                    })

    # Output results
    df_coint = pd.DataFrame(coint_pair_list)
    df_coint = df_coint[~df_coint['sym_1'].isin(bad_pairs) & ~df_coint['sym_2'].isin(bad_pairs)]

    return df_coint
