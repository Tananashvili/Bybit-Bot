from config_execution_api import z_score_window
from statsmodels.tsa.stattools import coint
import statsmodels.api as sm
import pandas as pd


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
def calculate_metrics(series_1, series_2):
    coint_flag = 0
    try:
        coint_res = coint(series_1, series_2)
        t_value = coint_res[0]
        p_value = coint_res[1]
        critical_value = coint_res[2][1]
        model = sm.OLS(series_1, series_2).fit()
        hedge_ratio = model.params[0]
        spread = calculate_spread(series_1, series_2, hedge_ratio)
        zscore_data = calculate_zscore(spread)
        zscore_list = zscore_data["z_scores"]
        if p_value < 0.05 and t_value < critical_value:
            coint_flag = 1

    except ValueError:
        print('Invalid input, x is constant')
        coint_flag = 0
        zscore_list = []

    return (coint_flag, zscore_list.tolist())
