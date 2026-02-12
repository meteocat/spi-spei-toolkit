"""
Utility functions to compute SPI and SPEI indices
for both point-based (time series) and grid-based datasets.
"""
import pandas as pd
import numpy as np
import xarray as xr
import scipy.stats as scs
from sklearn.mixture import GaussianMixture


# --- Data preparation (point)
def data_preparation(data:pd.Series,acc_time:int)->pd.Series:
    """
    Apply an accumulation window to point-based data for SPI or SPEI
    calculation.

    Args:
        data (pd.Series): Input time series with DatetimeIndex.
        acc_time (int): Accumulation period in days.

    Returns:
        pd.Series: Accumulated time series.
    """    
    data_prep = data.interpolate().rolling(
        window=acc_time,
        min_periods=acc_time).sum().dropna()
    return data_prep



# --- Data preparation (grid)
def data_preparation_malla(data:xr.Dataset,acc_time:int)->xr.Dataset:
    """
    Apply an accumulation window to grid-based data for SPI or SPEI
    calculation.

    Args:
        data (xr.Dataset): Input dataset with dimensions (date, lat, lon).
        acc_time (int): Accumulation period in days.

    Returns:
        xr.Dataset: Accumulated dataset.
    """    
    data_prep = data.rolling(date=acc_time,min_periods=acc_time).sum()

    return data_prep



# --- Distribution fitting
def fit_distribution(data:pd.Series | np.ndarray,dist_name:str)->tuple:
    """
    Fit a parametric probability distribution to the input data.
    
    Args:
        data (pd.Series | np.ndarray): Input data values.
        dist_name (str): Distribution name (scipy.stats compatible).

    Returns:
        tuple: Fitted distribution parameters.
    """
    dist = getattr(scs, dist_name)

    if dist_name == "gamma":
        clean_data = data[np.isfinite(data) & (data > 0)]  
        if len(clean_data)>0:
            params = dist.fit(clean_data,floc=0,
                              scale=np.std(clean_data))
        else:
            params = (np.nan,np.nan,np.nan)
            
    else:  
        params = dist.fit(data,scale=np.std(data))

    return params



# --- Gaussian Mixture fitting
def fit_gaussian_mixture(data:pd.Series | np.ndarray, n_components=2)->tuple:
    """
    Fit a Gaussian Mixture Model (GMM) to the input data.

    Args:
        data (pd.Series | np.ndarray): Input data.
        n_components (int, optional): Number of Gaussian components.

    Returns:
        tuple: Means, standard deviations and weights of each component.
    """    
    data = data[~np.isnan(data)]  

    if len(data) < n_components:
        return ([np.nan] * n_components, 
                [np.nan] * n_components, 
                [np.nan] * n_components)

    gmm = GaussianMixture(n_components=n_components, random_state=42)
    if not isinstance(data,np.ndarray):
        data = np.array(data)
    gmm.fit(data.reshape(-1, 1))
    
    means = gmm.means_.flatten()
    stds = np.sqrt(gmm.covariances_.flatten())
    weights = gmm.weights_.flatten()

    return means, stds, weights



# --- SPEI (point)
def calculate_spei(data:pd.Series,dist_name:str,params:tuple)->pd.Series:
    """
    Compute the SPEI index for point-based data.

    Args:
        data (pd.Series): Input accumulated series.
        dist_name (str): Distribution name (scipy.stats compatible).
        params (tuple): Distribution parameters

    Returns:
        pd.Series: SPEI time series.
    """    
    if dist_name == "GaussianMixture":
        means,stds,weights = params 
           
        cdf = sum(
            weights[i] * scs.norm.cdf(data, loc=means[i], scale=stds[i])
            for i in range(len(weights))
        )
        
    else:
        cdf = getattr(scs, dist_name).cdf(data,*params)
        
    cdf = np.where(cdf == 0, 1e-6, cdf)
    cdf = xr.where(cdf == 1, 1 - 1e-6, cdf)

    spei = scs.norm.ppf(cdf,loc=0,scale=1)
    spei = pd.Series(spei,index=data.index)
    return spei



# --- SPEI (grid)
def calculate_spei_malla(data:xr.DataArray,dist_name:str,
                         params:xr.Dataset)->xr.Dataset:
    """
    Compute the SPEI index for grid-based data.

    Args:
        data (xr.DataArray): Accumulated grid data.
        dist_name (str): Distribution name (scipy.stats compatible)
        params (xr.Dataset): Grid-based distribution parameters.

    Returns:
        xr.Dataset: SPEI grid.
    """    
    if dist_name == "GaussianMixture":
        means = params["means"]
        stds = params["stds"]
        weights = params["weights"]       
        
        cdf = 0
        for i in params.component.values:
            weight_i = weights.sel(component=i).broadcast_like(
                data).transpose("date", "lat", "lon")
            cdf += weight_i * scs.norm.cdf(data, loc=means.sel(component=i),
                                           scale=stds.sel(component=i))
        
    else:
         
        cdf = getattr(scs, dist_name).cdf(data,params["shape"],
                                          params["location"],
                                          params["scale"])
    cdf = xr.where(cdf == 0, 1e-6, cdf)
    cdf = xr.where(cdf == 1, 1 - 1e-6, cdf)
    
    spei = scs.norm.ppf(cdf,loc=0,scale=1)
    spei_grid = xr.DataArray(spei, dims=["date", "lat", "lon"],
                              coords={"date": data.date.values,
                                      "lat":data.lat,"lon":data.lon},
                              name="SPEI").to_dataset()
    return spei_grid



# --- SPI (point)
def calculate_spi(data:pd.Series,dist_name:str,params:tuple)->pd.Series:
    """
    Compute the SPI index for point-based data.

    Args:
        data (pd.Series): Input accumulated series.
        dist_name (str): Distribution name (scipy.stats compatible).
        params (tuple): Distribution parameters.

    Returns:
        pd.Series: SPI time series.
    """   
    if (dist_name == "gamma"):
        prob_zero = len(data[data==0])/len(data)
        data[(data>0)&(data<1)] = 1  
        cdf = getattr(scs, dist_name).cdf(data,*params)
        cdf = prob_zero + (1 - prob_zero)*cdf
    else:
        cdf = getattr(scs, dist_name).cdf(data,*params)
        cdf = np.where(cdf == 0, 1e-6, cdf)
        
    spi = scs.norm.ppf(cdf,loc=0,scale=1)
    spi = pd.Series(spi,index=data.index)
    return spi



# --- SPI (grid)
def calculate_spi_malla(data:xr.DataArray,dist_name:str,
                        params:xr.Dataset)->pd.Series:
    """
    Compute the SPI index for grid-based data.

    Args:
        data (xr.DataArray): Accumulated grid data.
        dist_name (str): Distribution name (gamma for SPI).
        params (xr.Dataset): Grid-based distribution parameters.

    Returns:
        xr.Dataset: SPI grid.
    """ 
    if (dist_name == "gamma"):
        prob_zero = (data == 0).mean(dim="date").broadcast_like(data)
        data = data.where(data >= 1, 1) 

        cdf = getattr(scs, dist_name).cdf(data,params["shape"], 
                                          params["location"],params["scale"])
        cdf = prob_zero + (1 - prob_zero)*cdf 
    else: 
        cdf = getattr(scs, dist_name).cdf(data,params["shape"],
                                          params["location"],params["scale"])
        cdf = xr.where(cdf == 0, 1e-6, cdf)
        cdf = xr.where(cdf == 1, 1 - 1e-6, cdf)
        
    spi = scs.norm.ppf(cdf,loc=0,scale=1)
    spi_grid = xr.DataArray(spi, dims=["date", "lat", "lon"],
                             coords={"date": data.date.values,
                                      "lat":data.lat,"lon":data.lon},
                             name="SPI").to_dataset()
    return spi_grid



# --- Monthly parameters (general distribution)
def compute_monthly_params(monthly_data:xr.DataArray,dist_name:str)->xr.Dataset:
    """
    Fit a parametric distribution to each grid point using xr.apply_ufunc.

    Args:
        monthly_data (xr.DataArray): Grid data.
        dist_name (str): Distribution name.

    Returns:
        xr.Dataset: Grid of distribution parameters (shape, location, scale).
    """    
    shape, loc, scale = xr.apply_ufunc(
        fit_distribution,
        monthly_data,
        input_core_dims=[["date"]],
        output_core_dims=[[], [], []],
        vectorize=True,
        kwargs={"dist_name": dist_name}
    )
    return xr.Dataset({"shape": shape, "location": loc, "scale": scale})



# --- Monthly parameters (Gaussian Mixture)
def compute_monthly_params_GM(monthly_data:xr.DataArray)->xr.Dataset:
    """
    Fit a Gaussian Mixture distribution to each grid point.
    
    Args:
        monthly_data (xr.DataArray): Grid data.
        
    Returns:
        xr.Dataset:  Grid of GMM parameters (means, stds, weights).
    """    
    nlat = len(monthly_data.lat)
    nlon = len(monthly_data.lon)
    ncomp = 2
    means_vals = np.full((nlat, nlon, ncomp), np.nan)
    stds_vals = np.full((nlat, nlon, ncomp), np.nan)
    weights_vals = np.full((nlat, nlon, ncomp), np.nan)

    for i, lat in enumerate(monthly_data.lat.values):
        for j, lon in enumerate(monthly_data.lon.values):
            values = monthly_data.sel(lat=lat, lon=lon).values
            if not np.all(values==0):
                means, stds, weights = fit_gaussian_mixture(values, 
                                                            n_components=ncomp)
            else:
                means, stds, weights = np.nan,np.nan,np.nan

            means_vals[i, j, :] = means
            stds_vals[i, j, :] = stds
            weights_vals[i, j, :] = weights

    means_da = xr.DataArray(means_vals, coords=[monthly_data.lat,
                                                monthly_data.lon, 
                                                np.arange(ncomp)], 
                            dims=["lat", "lon", "component"])
    stds_da = xr.DataArray(stds_vals, coords=[monthly_data.lat, 
                                              monthly_data.lon, 
                                              np.arange(ncomp)],
                           dims=["lat", "lon", "component"])
    weights_da = xr.DataArray(weights_vals, coords=[monthly_data.lat, 
                                                    monthly_data.lon,
                                                    np.arange(ncomp)], 
                              dims=["lat", "lon", "component"])

    return xr.Dataset({"means":means_da,"stds":stds_da,"weights":weights_da})


