import numpy as np
import pandas as pd
import xarray as xr

from spei.core.spei_spi_functions import (
    data_preparation_grid,
    fit_distribution,
    fit_gaussian_mixture,
    compute_monthly_params,
    calculate_spi_grid,
    calculate_spei_grid
)

# ------------------------------------------------------------------
# DATA PREPARATION GRID
# ------------------------------------------------------------------

def test_data_preparation_grid():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    lat = [0.0, 1.0]
    lon = [0.0, 1.0]

    values = np.ones((10, 2, 2))

    ds = xr.Dataset(
        {"value": (("date", "lat", "lon"), values)},
        coords={"date": dates, "lat": lat, "lon": lon}
    )

    acc = data_preparation_grid(ds, acc_time=5)

    assert np.isnan(acc.value.isel(date=0)).all()

    assert acc.value.isel(date=5, lat=0, lon=0) == 5.0


# ------------------------------------------------------------------
# FIT DISTRIBUTION
# ------------------------------------------------------------------

def test_fit_distribution_gamma():
    data = np.array([1, 2, 3, 4, 5], dtype=float)

    shape, loc, scale = fit_distribution(data, "gamma")

    assert np.isfinite(shape)
    assert np.isfinite(loc)
    assert np.isfinite(scale)


# ------------------------------------------------------------------
# FIT GAUSSIAN MIXTURE
# ------------------------------------------------------------------

def test_fit_gaussian_mixture():
    data = np.array([1, 2, 3, 10, 11, 12], dtype=float)

    means, stds, weights = fit_gaussian_mixture(data, n_components=2)

    assert len(means) == 2
    assert len(stds) == 2
    assert len(weights) == 2

    assert np.isclose(weights.sum(), 1.0)
    assert np.all(np.isfinite(means))


# ------------------------------------------------------------------
# COMPUTE MONTHLY PARAMS
# ------------------------------------------------------------------

def test_compute_monthly_params_gamma():
    dates = pd.date_range("2000-01-01", periods=24, freq="M")
    lat = [0.0]
    lon = [0.0]

    values = np.random.rand(24, 1, 1) + 1.0

    da = xr.DataArray(
        values,
        dims=("date", "lat", "lon"),
        coords={"date": dates, "lat": lat, "lon": lon},
        name="value"
    )

    da = da.assign_coords(month=("date", da.date.dt.month.data))

    params = compute_monthly_params(da, dist_name="gamma")

    assert "shape" in params
    assert "location" in params
    assert "scale" in params


# ------------------------------------------------------------------
# SPI GRID
# ------------------------------------------------------------------

def test_calculate_spi_grid():
    dates = pd.date_range("2000-01-01", periods=12, freq="M")
    lat = [0.0]
    lon = [0.0]

    data_vals = np.random.rand(12, 1, 1) * 10 + 1

    data = xr.DataArray(
        data_vals,
        dims=("date", "lat", "lon"),
        coords={"date": dates, "lat": lat, "lon": lon}
    )

    params = xr.Dataset(
        {
            "shape": (("lat", "lon"), np.array([[2.0]])),
            "location": (("lat", "lon"), np.array([[0.0]])),
            "scale": (("lat", "lon"), np.array([[5.0]]))
        },
        coords={"lat": lat, "lon": lon}
    )

    spi = calculate_spi_grid(data, "gamma", params)

    assert "SPI" in spi
    assert np.all(np.isfinite(spi["SPI"].values))


# ------------------------------------------------------------------
# SPEI GRID
# ------------------------------------------------------------------

def test_calculate_spei_grid_GM():
    dates = pd.date_range("2000-01-01", periods=12, freq="M")
    lat = [0.0]
    lon = [0.0]

    data_vals = np.linspace(-10, 10, 12).reshape(12, 1, 1)
    data = xr.DataArray(
        data_vals,
        dims=("date", "lat", "lon"),
        coords={"date": dates, "lat": lat, "lon": lon}
    )

    params = xr.Dataset(
        {
            "means": (("lat", "lon", "component"), np.array([[[ -5.0, 5.0]]])),
            "stds": (("lat", "lon", "component"), np.array([[[1.0, 1.0]]])),
            "weights": (("lat", "lon", "component"), np.array([[[0.5, 0.5]]]))
        },
        coords={
            "lat": lat,
            "lon": lon,
            "component": [0, 1]
        }
    )

    spei = calculate_spei_grid(data, "GaussianMixture", params)

    assert "SPEI" in spei
    assert np.all(np.isfinite(spei["SPEI"].values))
