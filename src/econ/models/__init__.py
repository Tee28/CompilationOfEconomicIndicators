"""Models: config (spec.py), as-of datasets (data.py), fits (fit.py), runner + `econ forecast` (run.py).

Card: docs/models/live-slice.md. Contract: schemas.ForecastRecord / HorizonForecast (ADR 0001).
"""
from .run import Context, MarketRun, cmd_forecast, context, forecast, forecast_all, run_market  # noqa: F401
