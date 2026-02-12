"""
Operational calculation of SPI and SPEI indices on a grid (xarray-based).
"""
import pandas as pd
import xarray as xr
import datetime
from pathlib import Path
import argparse
from spei.utils.logger import create_static_logger
from spei.utils.load_config import load_config
import spei.core.spei_spi_functions as sf

LOGGER = None
LOGGER_TRACE = None
CONFIG = None

PARSER = argparse.ArgumentParser(
   description='Grid-based SPEI / SPI calculation')
PARSER.add_argument('-c', '--config', help='Configuration file', type=str,
                   required=True)
PARSER.add_argument('-d', '--date',
                   help='Target date(YYYYmmdd)', type=str, required=True)
PARSER.add_argument('-i', '--index_name',
                   help='Index name: SPI or SPEI', type=str, required=True)


def main():
    LOGGER.info(f"< Start {index_name} calculation >")
      
    ref_params_period = CONFIG["ref_params_period"]
     
    year = date[0:4]
    month = date[4:6]
    date_dt = datetime.datetime.strptime(date,"%Y%m%d")
    
    workdir = Path(CONFIG["workdir"])
    params_dir = Path(CONFIG["params_dir"])
    out_dir = workdir / index_name / year / month
    out_dir.mkdir(parents=True, exist_ok=True)
   
    # Accumulation periods (months -> equivalent days)
    acc_time_dic = {1:30, 3:90, 6:180, 9:270, 12:365, 18:545, 24:730, 36:1095}
    
    distribution_name = CONFIG["distribution_name"][index_name]
    indices = CONFIG["indices"]
    
    
    for index_type in indices:
        LOGGER.info(f" |  Start {index_name}-{index_type}")
        accumulation_time = acc_time_dic[index_type]
        date_inici = date_dt - datetime.timedelta(accumulation_time)
        dates = pd.date_range(date_inici,date_dt).strftime("%Y%m%d")

        # --- Load precipitation grids
        ppt_files = [Path(CONFIG["ppt_file"].format_map(
            {"year":d[0:4],"month":d[4:6],"day":d[6:8],"date":d})) 
                     for d in dates]
        
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
                LOGGER_TRACE.error("Error loading ET0 grids': %s",
                                   err,exc_info=True)
                raise
            
            data = ppt - eto.eto
            
        # --- SPI: precipitation only    
        elif (index_name == "SPI"):
            data = ppt

        data = data.rename({"ppt":"value"})
        data = data.dropna(dim="date",how="all")
        
        # --- Accumulation
        try:
            acc_data = sf.data_preparation_malla(data=data,
                                                 acc_time=accumulation_time)
            LOGGER.info(" |  Accumulated data - ok")
        except Exception as err:
            LOGGER.error(" |  Error during accumulation step. Check trace")    
            LOGGER_TRACE.error("Error during accumulation step': %s",
                               err,exc_info=True)
            raise
        
        # --- Load distribution parameters
        params_file = (
            params_dir / 
            f"params_{ref_params_period}_{index_name}{index_type}_{distribution_name}.nc")
        
        if not params_file.exists():
            LOGGER.error(f" |  Parameter file not found: {params_file}")
            raise FileNotFoundError(params_file)
        
        
        try:
            params = xr.open_dataset(params_file)
            LOGGER.info(" |  Distribution parameters - ok")
        except Exception as err:
            LOGGER.error(" |  Error loading distribution parameters. Check trace")    
            LOGGER_TRACE.error("Error loading distribution parameters': %s",
                               err,exc_info=True)
            raise
        
        acc_data = acc_data.load()
        
        
        # --- Index calculation  
        try:  
            if (index_name=="SPI"):
                index_values = acc_data.value.groupby(
                    acc_data.date.dt.month).apply(
                        lambda x: sf.calculate_spi_malla(
                            x,
                            distribution_name,
                            params.sel(month=x.date.dt.month.values[0], 
                                       method="nearest")))
                LOGGER.info(" |  SPI - ok")
                output_name = (
                    f"{index_name}{index_type}_{distribution_name}"
                    f"_ref_{ref_params_period}_{date}.nc"
                    )

            elif (index_name=="SPEI"): 
                index_values = acc_data.value.groupby(
                    acc_data.date.dt.month).apply(
                        lambda x: sf.calculate_spei_malla(
                            x,
                            distribution_name, 
                            params.sel(month=x.date.dt.month.values[0],
                                       method="nearest")))        
                LOGGER.info(" |  SPEI - ok")
                output_name = (
                    f"{index_name}{index_type}_{distribution_name}_{date}.nc"
                    )
                
        except Exception as err:
            LOGGER.error(f" |  Error computing {index_name}. Check trace")    
            LOGGER_TRACE.error(f"Error computing {index_name}': %s",
                               err,exc_info=True)
            raise
 
 
        # --- Save result
        index_values = index_values.sel(date=date)  
        output_path = out_dir / output_name   
        
        if output_path.exists():
            LOGGER.info(f" |  Existing file removed: {output_path}")
            output_path.unlink()

        index_values.to_netcdf(output_path)
        
        LOGGER.info(f" |  Finished {index_name}-{index_type}")
        LOGGER.info(" ")
    
    LOGGER.info(f"< End {index_name} calculation />")
    LOGGER.info(" ")

        
if __name__ == "__main__":
    ARGS = PARSER.parse_args()
    date = ARGS.date
    index_name = ARGS.index_name
    
    if index_name not in ("SPI", "SPEI"):
        raise ValueError(
            "index_name must be 'SPI' or 'SPEI'"
        )
    
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
        Path(CONFIG["log_dir"])/"spi_spei_trace.log",
        "spi_spei_trace"
        )      
    
    main()
