"""
Point-based calculation of distribution parameters for SPI and SPEI
over a reference period.
"""
import argparse
import pickle
import datetime
import pandas as pd
from pathlib import Path
import spei.core.spei_spi_functions as sf
from spei.utils.logger import create_static_logger
from spei.utils.load_config import load_config

LOGGER = None
LOGGER_TRACE = None
CONFIG = None

PARSER = argparse.ArgumentParser(
   description='Point-based distribution parameter calculation for SPEI / SPI')
PARSER.add_argument('-c', '--config', help='Configuration file', type=str,
                   required=True)
PARSER.add_argument('-i', '--index_name',
                   help='Index name: SPI or SPEI', type=str, required=True)

def main(index_name):
    LOGGER.info(f"< Start parameter calculation for {index_name} >")

    # --- Paths
    out_dir = Path(CONFIG["params_dir"])
   
    # --- Configuration parameters
    years_ref = CONFIG["ref_params_period"]
    ref_period = (years_ref[0:4],years_ref[5:9])
    start_ref = datetime.datetime(int(ref_period[0]), 1, 1)
    end_ref   = datetime.datetime(int(ref_period[1]), 12, 31)

    dates = pd.date_range(start=start_ref, 
                      end=end_ref, 
                      freq="D").strftime("%Y%m%d")
 
    code = CONFIG["code"]
    indices = CONFIG["indices"]
    distribution_name = CONFIG["distribution_name"][index_name]

    # --- Accumulation periods (months -> equivalent days)
    acc_time_dic = {1:30, 3:90, 6:180, 9:270, 12:365, 18:545, 24:730, 36:1095}
    
    # --- Load data
    ppt_files = [Path(CONFIG["ppt_file"].format_map(
            {"year":e[0:4],"month":e[4:6],"day":e[6:8],"date":e,"code":code}))
                        for e in dates]
    
    try:        
        ppt = pd.concat((pd.read_csv(f) for f in ppt_files),
                        ignore_index=True)
        LOGGER.info(" |  PPT - ok")
    except Exception as err:
        LOGGER.error(" |  Error loading precipitation data. Check trace")    
        LOGGER_TRACE.error("Error loading precipitation data: %s",
                            err,exc_info=True)
        raise
    
    # --- SPEI: subtract ET0
    if (index_name == "SPEI"):
        eto_files = [Path(CONFIG["eto_file"].format_map(
            {"year":e[0:4],"month":e[4:6],"day":e[6:8],"date":e,"code":code}))
                        for e in dates]
        
        missing = [p for p in eto_files if not p.exists()]
        
        if missing:
            for p in missing:
                LOGGER.error(f" |  Missing ET0 file: {p}")
                raise FileNotFoundError("Missing ET0 files")
            
        try:        
            eto = pd.concat((pd.read_csv(f) for f in eto_files),
                            ignore_index=True)
            LOGGER.info(" |  ET0 - ok")
        except Exception as err:
            LOGGER.error(" |  Error loading ET0 grids. Check trace")    
            LOGGER_TRACE.error("Error loading ET0 grids': %s",
                                err,exc_info=True)
            raise
        
        data = pd.merge(ppt,eto,on="date")
        data["value"] = data["ppt"]-data["eto"]      
    
    # --- SPI: precipitation only    
    elif (index_name == "SPI"):
        data = ppt
        data = data.rename(columns={"ppt":"value"})
        
    data = data[["date","value"]]
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date")
    data.set_index("date",inplace=True)


    # --- Loop over accumulation periods
    for index_type in indices:
        LOGGER.info(f" |  Start {index_name}-{index_type}")
        accumulation_time = acc_time_dic[index_type]
        
        try:
            df = sf.data_preparation(data=data,acc_time=accumulation_time)  
            LOGGER.info(" |  Accumulated data - ok")
        except Exception as err:
            LOGGER.error(" |  Error during accumulation step. Check trace")    
            LOGGER_TRACE.error("Error during accumulation step: %s",
                               err,exc_info=True)
            raise
        
        # --- Fit distribution parameters
        try:
            if (distribution_name=="GaussianMixture"):
                params = df.groupby(df.index.month).apply(lambda x:
                    sf.fit_gaussian_mixture(x)).to_dict()
            else:
                params = df.groupby(df.index.month).apply(lambda x:
                    sf.fit_distribution(x,distribution_name)).to_dict()
            LOGGER.info(" |  Distribution parameters - ok")            
        except Exception as err:
            LOGGER.error(" |  Error computing distribution parameters. Check trace")    
            LOGGER_TRACE.error("Error computing distribution parameters: %s",
                               err,exc_info=True)
            raise

        # --- Save output
        filename = (
            f"params_{years_ref}_{index_name}"
            f"{index_type}_{distribution_name}_{code}.pkl"
            )
        file_path = out_dir / filename   
        pickle.dump(params,open(file_path,"wb"))   
          
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
        Path(CONFIG["log_dir"]) / "spi_spei_point.log",
        "spi_spei_point"
        )
    LOGGER_TRACE = create_static_logger(
        Path(CONFIG["log_dir"]) / "spi_spei_point_trace.log",
        "spi_spei_point_trace"
        ) 

    main(index_name)