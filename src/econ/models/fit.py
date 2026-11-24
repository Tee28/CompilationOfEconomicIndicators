"""Pure numpy fits (deterministic, no randomness): L2 logistic (Newton) and ridge, intercept unpenalised.

Features are composite levels (already expanding z-scores), so they are NOT re-standardised: the contribution
of a feature at the origin is simply coef x value (log-odds for the logit, log-return for the ridge).
"""
from __future__ import annotations

import numpy as np


def logit_ridge(X: np.ndarray, y: np.ndarray, l2: float, iters: int = 100, tol: float = 1e-10):
    """min sum NLL + l2/2 * ||b||^2 ; returns (intercept, coefs)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, k = X.shape
    A = np.column_stack([np.ones(n), X])
    pen = np.full(k + 1, float(l2))
    pen[0] = 1e-8  # intercept effectively unpenalised (tiny ridge keeps all-0/all-1 samples finite)
    pbar = np.clip(y.mean(), 1e-3, 1 - 1e-3)
    w = np.zeros(k + 1)
    w[0] = np.log(pbar / (1 - pbar))
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(A @ w, -30, 30)))
        g = A.T @ (p - y) + pen * w
        H = (A * (p * (1 - p))[:, None]).T @ A + np.diag(pen)
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < tol:
            break
    return float(w[0]), w[1:]


def ridge(X: np.ndarray, y: np.ndarray, l2: float):
    """min ||y - a - Xb||^2 + l2 ||b||^2 (centred closed form); returns (intercept, coefs)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mx, my = X.mean(axis=0), y.mean()
    Xc = X - mx
    b = np.linalg.solve(Xc.T @ Xc + l2 * np.eye(X.shape[1]), Xc.T @ (y - my))
    return float(my - mx @ b), b


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
