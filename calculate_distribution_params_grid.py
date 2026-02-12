"""
Grid-based calculation of distribution parameters for SPI and SPEI
over a reference period.
"""
import xarray as xr
import pandas as pd
import numpy as np 
import argparse
from pathlib import Path
import spei.core.spei_spi_functions as sf
from spei.utils.logger import create_static_logger
from spei.utils.load_config import load_config

LOGGER = None
LOGGER_TRACE = None
CONFIG = None

PARSER = argparse.ArgumentParser(
   description='Grid-based distribution parameter calculation for SPEI / SPI')
PARSER.add_argument('-c', '--config', help='Configuration file', type=str,
                   required=True)
PARSER.add_argument('-i', '--index_name',
                   help='Index name: SPI or SPEI', type=str, required=True)


def main():
    LOGGER.info(f"< Start parameter calculation for {index_name} >")

    # --- Paths
    out_dir = Path(CONFIG["params_dir"])
    
    # --- Configuration parameters
    years_ref = CONFIG["ref_params_period"]
    ref_period = (years_ref[0:4],years_ref[5:9])
    dates = pd.date_range(start=ref_period[0], 
                          end=ref_period[1], 
                          freq="d").strftime("%Y%m%d")
    
    # --- Accumulation periods (months -> equivalent days)
    acc_time_dic = {1:30, 3:90, 6:180, 9:270, 12:365, 18:545, 24:730, 36:1095}
    
    distribution_name = CONFIG["distribution_name"][index_name]
    indices = CONFIG["indices"]
    
    try:
        nan_mask = xr.open_dataarray(CONFIG["dir_mask"])
        LOGGER.info(" |  NaN mask - ok")
    except Exception as err:
        LOGGER.error(" |  Error loading NaN mask. Check trace")    
        LOGGER_TRACE.error("Error loading NaN mask: %s",err,exc_info=True)
        raise
    
    # --- Load precipitation grids
    ppt_files = [Path(CONFIG["ppt_file"].format_map(
        {"year":d[0:4],"month":d[4:6],"day":d[6:8],"date":d})) for d in dates]
    missing = [p for p in ppt_files if not p.exists()]

    if missing:
        for p in missing:
            LOGGER.error(f" |  Missing precipitation file: {p}")
            raise FileNotFoundError("Missing precipitation files")
        
    try:        
        ppt = xr.open_mfdataset(ppt_files)
        LOGGER.info(" |  PPT - ok")
    except Exception as err:
        LOGGER.error(" |  Error loading precipitation grids. Check trace")    
        LOGGER_TRACE.error("Error loading precipitation grids: %s",
                           err,exc_info=True)
        raise
    
    
    # --- SPEI: subtract ET0  
    if (index_name == "SPEI"):
        eto_files = [Path(CONFIG["eto_file"].format_map(
            {"year":e[0:4],"month":e[4:6],"day":e[6:8],"date":e}))
                      for e in dates]
        missing = [p for p in eto_files if not p.exists()]
        
        if missing:
            for p in missing:
                LOGGER.error(f" |  Missing ET0 file: {p}")
                raise FileNotFoundError("Missing ET0 files")
            
        try:        
            eto = xr.open_mfdataset(eto_files)
            LOGGER.info(" |  ET0 - ok")
        except Exception as err:
            LOGGER.error(" |  Error loading ET0 grids. Check trace")    
            LOGGER_TRACE.error("Error loading ET0 grids: %s",
                               err,exc_info=True)
            raise
        
        data = ppt - eto.eto
        
    # --- SPI: precipitation only 
    elif (index_name == "SPI"):
        data = ppt

    data = data.rename({"ppt":"value"})
    data = data.dropna(dim="date",how="all")
    
    # --- Loop over accumulation periods
    for index_type in indices:
        LOGGER.info(f" |  Start {index_name}-{index_type}")
        accumulation_time = acc_time_dic[index_type]
        
        try:
            df = sf.data_preparation_malla(data=data, 
                                           acc_time=accumulation_time)  
            LOGGER.info(" |  Accumulated data - ok")
        except Exception as err:
            LOGGER.error(" |  Error during accumulation step. Check trace")    
            LOGGER_TRACE.error("Error during accumulation step: %s",
                               err,exc_info=True)
            raise

        df = df.load()
        df = df.dropna(dim="date",how="all") 
        df = xr.where(np.isnan(df),0,df) 

        df = df.assign_coords(month=("date", df["date"].dt.month.data))


        # --- Fit distribution parameters
        try:
            if (distribution_name=="GaussianMixture"):
                params = df.value.groupby("month").map(
                    sf.compute_monthly_params_GM
                    )
            else:
                params = df.value.groupby("month").map(
                    lambda x: sf.compute_monthly_params(
                        x, dist_name=distribution_name
                        )
                    )
            LOGGER.info(" |  Distribution parameters - ok")
            
        except Exception as err:
            LOGGER.error(" |  Error computing distribution parameters. Check trace")    
            LOGGER_TRACE.error("Error computing distribution parameters: %s",
                               err,exc_info=True)
            raise
        
        # --- Apply spatial mask    
        params = xr.where(np.isnan(nan_mask),np.nan,params)
        
        # --- Save output
        filename = (
            f"params_{years_ref}_{index_name}"
            f"{index_type}_{distribution_name}.nc"
            )
        file_path = out_dir / filename   

        params.to_netcdf(file_path)
        
        LOGGER.info(f" |  Finished {index_name}-{index_type}")
        LOGGER.info(" ")

    LOGGER.info(f"< End parameter calculation for {index_name} />")

        
        
if __name__ == "__main__":
    ARGS = PARSER.parse_args()
    index_name = ARGS.index_name
    
    if index_name not in ("SPI", "SPEI"):
        raise ValueError("index_name must be 'SPI' or 'SPEI'")
    
    try:
        CONFIG = load_config(ARGS.config)
    except Exception as err:
        print('Error while loading the configuration file.')
        print(err)
        CONFIG = load_config(
            "/path/to/default_config_file.json"
            )  

    LOGGER = create_static_logger(
        Path(CONFIG["log_dir"]) / "spi_spei.log",
        "spi_spei"
        )
    LOGGER_TRACE = create_static_logger(
        Path(CONFIG["log_dir"]) / "spi_spei_trace.log",
        "spi_spei_trace"
        ) 

    main()

        
