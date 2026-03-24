"""
models.py — Modelos Econométricos Espaciais: OLS, Spatial Error Model
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm


def run_ols_regression(gdf, target_col, feature_cols, verbose=True):
    """
    OLS (Ordinary Least Squares) para avaliar correlação entre
    variáveis socioespaciais e a incerteza da geocodificação.

    Args:
        gdf: GeoDataFrame
        target_col: Variável dependente (ex: 'GCI')
        feature_cols: Lista de variáveis independentes
        verbose: Imprimir summary

    Returns:
        model: Fitted OLS model
        summary_df: DataFrame com coeficientes
    """
    gdf_clean = gdf.dropna(subset=[target_col] + feature_cols).copy()

    Y = gdf_clean[target_col].astype(float)
    X = sm.add_constant(gdf_clean[feature_cols].astype(float))

    model = sm.OLS(Y, X).fit()

    if verbose:
        print(model.summary())

    # Extract coefficients to DataFrame
    summary_df = pd.DataFrame({
        'variable': model.params.index,
        'coef': model.params.values,
        'std_err': model.bse.values,
        'p_value': model.pvalues.values,
        'ci_low': model.conf_int()[0].values,
        'ci_high': model.conf_int()[1].values,
    })

    return model, summary_df


def run_spatial_error_model(gdf, target_col, feature_cols, weights):
    """
    Spatial Error Model (SEM) via PySAL/spreg.
    Isola a dependência espacial do termo de erro.

    y = Xβ + u, onde u = λWu + ε

    Args:
        gdf: GeoDataFrame
        target_col: Variável dependente
        feature_cols: Variáveis independentes
        weights: Matriz de pesos PySAL

    Returns:
        model: Fitted ML_Error model
    """
    import spreg

    gdf_clean = gdf.dropna(subset=[target_col] + feature_cols).copy()

    Y = gdf_clean[target_col].values.reshape(-1, 1).astype(float)
    X = gdf_clean[feature_cols].values.astype(float)

    model = spreg.ML_Error(
        Y, X, w=weights,
        name_y=target_col,
        name_x=feature_cols,
    )

    return model


def compare_models(ols_model, sem_model):
    """
    Compara OLS vs SEM: R², AIC, log-likelihood.

    Returns:
        DataFrame comparativo
    """
    comparison = pd.DataFrame({
        'Metric': ['R²', 'Adj. R²', 'AIC', 'BIC', 'Log-Lik', 'Lambda (SEM)'],
        'OLS': [
            ols_model.rsquared,
            ols_model.rsquared_adj,
            ols_model.aic,
            ols_model.bic,
            ols_model.llf,
            'N/A',
        ],
        'SEM': [
            sem_model.pr2 if hasattr(sem_model, 'pr2') else 'N/A',
            'N/A',
            sem_model.aic if hasattr(sem_model, 'aic') else 'N/A',
            'N/A',
            sem_model.logll if hasattr(sem_model, 'logll') else 'N/A',
            sem_model.lam if hasattr(sem_model, 'lam') else 'N/A',
        ]
    })
    return comparison
