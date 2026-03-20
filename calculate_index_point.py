"""
Operational calculation of SPI and SPEI indices on a point.
"""
import argparse
import datetime
import pickle
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import spei.core.spei_spi_plots as sp
import spei.core.spei_spi_functions as sf
from spei.utils.logger import create_static_logger
from spei.utils.load_config import load_config

LOGGER = None
LOGGER_TRACE = None
CONFIG = None

PARSER = argparse.ArgumentParser(
   description='Point-based SPEI / SPI calculation')
PARSER.add_argument('-c', '--config', help='Configuration file', type=str,
                   required=True)
PARSER.add_argument('-i', '--index_name',
                   help='Index name: SPI or SPEI', type=str, required=True)


def main(index_name):
    LOGGER.info(f"< Start {index_name} calculation >")
    
    start = datetime.datetime.strptime(CONFIG["start_date"],"%Y%m%d")
    end = datetime.datetime.strptime(CONFIG["final_date"],"%Y%m%d")
    ref_params_period = CONFIG["ref_params_period"]
    
    workdir = Path(CONFIG["workdir"])
    params_dir = Path(CONFIG["params_dir"])
    figure_dir = Path(CONFIG["figures_dir"])
    out_dir = workdir / index_name 
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Accumulation periods (months -> equivalent days)
    acc_time_dic = {1:30, 3:90, 6:180, 9:270, 12:365, 18:545, 24:730, 36:1095}

    distribution_name = CONFIG["distribution_name"][index_name]
    indices = CONFIG["indices"]
    code = CONFIG["code"]


    for index_type in indices:
        LOGGER.info(f" |  Start {index_name}-{index_type}")
        accumulation_time = acc_time_dic[index_type]
        first_date = start-datetime.timedelta(accumulation_time)
        dates = pd.date_range(first_date,end).strftime("%Y%m%d")

        # --- Load precipitation data
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
        
        # --- Accumulation
        try:
            acc_data = sf.data_preparation(data=data,acc_time=accumulation_time)
            LOGGER.info(" |  Accumulated data - ok")
        except Exception as err:
            LOGGER.error(" |  Error during accumulation step. Check trace")    
            LOGGER_TRACE.error("Error during accumulation step': %s",
                               err,exc_info=True)
            raise
                
        # --- Load distribution parameters
        params_file = (
            params_dir / 
            f"params_{ref_params_period}_{index_name}{index_type}_{distribution_name}_{code}.pkl")
        
        if not params_file.exists():
            LOGGER.error(f" |  Parameter file not found: {params_file}")
            raise FileNotFoundError(params_file)
        
        try:
            params = pickle.load(open(params_file,"rb"))
            LOGGER.info(" |  Distribution parameters - ok")
        except Exception as err:
            LOGGER.error(" |  Error loading distribution parameters. Check trace")    
            LOGGER_TRACE.error("Error loading distribution parameters': %s",
                               err,exc_info=True)
            raise
        
        
        # --- Index calculation  
        try:               
            if (index_name=="SPI"):
                index_values = acc_data.groupby(acc_data.index.month).apply(
                    lambda x: sf.calculate_spi(x,distribution_name,
                                params[x.name])).reset_index(level=0, drop=True).sort_index()
                LOGGER.info(" |  SPI - ok")
            elif (index_name=="SPEI"):
                index_values = acc_data.groupby(acc_data.index.month).apply(
                    lambda x: sf.calculate_spei(x,distribution_name,
                                params[x.name])).reset_index(level=0, drop=True).sort_index()
                LOGGER.info(" |  SPEI - ok")    
        except Exception as err:
            LOGGER.error(f" |  Error computing {index_name}. Check trace")    
            LOGGER_TRACE.error(f"Error computing {index_name}': %s",
                               err,exc_info=True)
            raise
             
                
        # --- Plot
        if CONFIG["index_plot"] == "True":
            figsize = tuple(CONFIG["figure_size"])
            figure_path = figure_dir / f"{index_name}{index_type}_{distribution_name}_{code}.png"
            sp.plot_index_point(index_name,index_values,index_type,code,
                                figsize=figsize,save_path=figure_path)
        
        # --- Save result
        index_values = index_values.rename(index_name)
        output_name = (f"{index_name}{index_type}_{distribution_name}"
                       f"_{CONFIG["start_date"]}_{CONFIG["final_date"]}_{code}.csv")
        output_path = out_dir / output_name    
        index_values.to_csv(output_path)
        
        LOGGER.info(f" |  Finished {index_name}-{index_type}")
        LOGGER.info(" ")
        
    LOGGER.info(f"< End {index_name} calculation />")
    LOGGER.info(" ")


        
if __name__ == "__main__":
    
    ARGS = PARSER.parse_args()
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
        Path(CONFIG["log_dir"]) / "spi_spei_point.log",
        "spi_spei_point"
        )
    
    LOGGER_TRACE = create_static_logger(
        Path(CONFIG["log_dir"])/"spi_spei_point_trace.log",
        "spi_spei_point_trace"
        )      
    
    main(index_name)