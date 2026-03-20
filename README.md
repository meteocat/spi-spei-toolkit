# SPI & SPEI Calculation Toolkit

![License](https://img.shields.io/badge/license-GPL%203.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)

This repository provides a Python toolkit to compute the **Standardized Precipitation Index (SPI)** and the **Standardized Precipitation Evapotranspiration Index (SPEI)** for both point-based time series and grid-based datasets. 

---

## Features

- Compute **SPI** and **SPEI** at **daily resolution**, unlike most traditional monthly approaches.
- Handle both **point-based time series** and **grid-based datasets**.
- Support for multiple accumulation periods.
- Fit different **statistical distributions**: Gamma, Pearson III, Fisk, and Gaussian Mixture Models.
- Grid-based calculations compatible with **Xarray datasets**.
- Designed for **operational workflows** using daily input files

---

## Project Structure

```
spi_spei_toolkit/
│
├── calculate_index_grid.py                 # Entry script for grid-based calculations
├── calculate_distribution_params_grid.py   # Grid-based distribution parameter calculation
├── calculate_index_point.py                # Entry script for point-based calculations
├── calculate_distribution_params_point.py  # Point-based distribution parameter calculation
│
├── core/                                   # Core calculation functions
│   └── spei_spi_functions.py               # Utility functions for SPI and SPEI
│   └── spei_spi_plots.py                   # Utility functions for SPI and SPEI time-series plot
│
├── utils/                                  # Helper utilities
│   ├── logger.py                           # Logger setup
│   └── load_config.py                      # Configuration loader
│
├── configs/                                # Configuration files
│   └── config_grid_example.json
│   └── config_point_example.json
│
├── tests/                                  # Unit tests
│   └── test_spei_basic.py
│
└── README.md                               # This file
```

## Requirements

- Python 3.10+ (tested with Python 3.12)
- Required packages: numpy, pandas, xarray, scipy, scikit-learn.
- For testing: pytest.

You can install all dependencies via `conda` or `pip`. Example using `conda`:

```
conda create -n spi_spei python=3.12
conda activate spi_spei
conda install numpy pandas xarray scipy scikit-learn pytest -c conda-forge
```

## Configuration
All configurable parameters are stored in JSON files inside the configs/ folder.
Two examples are provided: one for grid-based processing and one for point-based processing.

### Grid-based config (config_grid_example.json)
Example:
```
{
"indices":[1,3,6,9,12,18,24,36],
"distribution_name":{"SPEI":"GaussianMixture","SPI":"gamma"},
"ref_params_period":"2000-2020",
"workdir":"/path/to/workdir",
"ppt_file":"/path/to/ppt_dir/{year}/{month}/ppt_{date}.nc",
"eto_file":"/path/to/eto_dir/{year}/{month}/eto_{date}.nc",
"params_dir":"/path/to/parameters",
"dir_mask":"/path/to/nan_mask.nc",
"log_dir":"/path/to/logs"
}
```

Key parameters:
- indices: Accumulation periods (in months) used to compute SPI and SPEI.
- distribution_name: Statistical distribution fitted for each index (recommended: gamma for SPI and GaussianMixture for SPEI).
- ref_params_period: Reference period (years) used to fit the statistical distributions.
- workdir: Root working directory of the project.
- ppt_file / eto_file: File path templates used to locate daily NetCDF files. These paths support
dynamic placeholders:
    - {year} → four-digit year (e.g., 2020)
    - {month} → two-digit month (e.g., 01–12)
    - {date} → full date string (e.g., 20200115)

    This design allows users to adapt the naming convention to their own datasets and enables automated daily processing workflows.
- params_dir: Directory where fitted distribution parameters are stored.
- dir_mask: NetCDF mask file used to exclude invalid grid cells.
- log_dir: Directory where log files are written.


### Point-based config (config_point_example.json)
Example:
```
{
"indices":[1,3,6,9,12,18,24,36],
"code":"station_code",
"start_date":"YYYYmmdd",
"final_date":"YYYYmmdd",
"distribution_name":{"SPEI":"GaussianMixture","SPI":"gamma"},
"ref_params_period":"2000-2020",
"index_plot":"True",
"figure_size":[12,4],
"workdir":"/path/to/workdir",
"figures_dir":"/path/to/figures",
"ppt_file":"/path/to/ppt_dir/{year}/{month}/ppt_{date}.nc",
"eto_file":"/path/to/eto_dir/{year}/{month}/eto_{date}.nc",
"params_dir":"/path/to/parameters",
"log_dir":"/path/to/logs"
}
```

Key parameters for point-based config:
- code: Station identifier.
- start_date / final_date: Period to process.
- index_plot: "True" to automatically generate time series plots.
- figure_size: Tuple [width, height] to define plot size.
- figures_dir: Directory to save generated plots.

Other fields are similar to the grid-based config.

## Data requirements

### Grid-based data
For grid-based processing, input precipitation (`ppt_file`) and evapotranspiration (`eto_file`) datasets must:

- Be in NetCDF format
- Share the same grid dimensions
- Have consistent latitude and longitude coordinates
- Use the same coordinate reference system
- Include a valid `date` coordinate

The toolkit concatenates daily files along the `date` dimension.  
If dimensions or coordinates do not match, the processing will fail or produce incorrect results.

---

### Point-based data
For point-based processing, input data must be provided as **daily CSV files**, typically one file per day.

Each file should contain at least:

- A `date` column (or equivalent, convertible to datetime)
- A precipitation column (`ppt`)
- (Optional for SPEI) an evapotranspiration column (`eto`)

Example structure:

date,ppt,eto<br>
2025-01-01,2.3,0.8<br>
2025-01-02,0.0,1.1<br>
...

Notes:
- Data must represent a **single location (station)**.
- The toolkit concatenates all daily files into a continuous time series.
- The time series is:
  - Sorted by date
  - Converted to daily frequency
  - Used to compute rolling accumulations
- Optional: generate time-series plots for each station automatically.

Missing values:
- Short gaps can be interpolated internally (configurable in code)
- Long gaps may affect index reliability



## Usage
### Grid-based parameter calculation
Fits statistical distributions for each grid cell using a reference period.
```
python calculate_distribution_params_grid.py -c configs/config_grid_example.json -i SPEI
python calculate_distribution_params_grid.py -c configs/config_grid_example.json -i SPI
```
### Grid-based index calculation
Computes daily SPI or SPEI values for each grid point using the fitted distribution parameters.
```
python calculate_index_grid.py -c configs/config_grid_example.json -d YYYYmmdd -i SPEI
python calculate_index_grid.py -c configs/config_grid_example.json -d YYYYmmdd -i SPI
```

### Point-based parameter calculation
Fits statistical distributions using a reference period for a single station time series.
```
python calculate_distribution_params_point.py -c configs/config_point_example.json -i SPEI
python calculate_distribution_params_point.py -c configs/config_point_example.json -i SPI
```
### Point-based index calculation
Computes daily SPI or SPEI values from accumulated time series using previously fitted parameters.
```
python calculate_index_point.py -c configs/config_point_example.json -i SPEI
python calculate_index_point.py -c configs/config_point_example.json -i SPI
```


## Output
### Grid-based outputs
The grid-based scripts generate NetCDF files containing:

- Fitted distribution parameters
- Daily SPI or SPEI values for each grid point

### Point-based outputs
The point-based scripts generate CSV files containing:
- Daily SPI or SPEI values for the selected station
- Optional time series plots (PNG format)


## Testing
Unit tests are available in the `tests/` directory.

Run all tests with:

```
pytest
```

Run a specific test file:
```
pytest -v tests/test_spei_basic.py
```


## License
This project is licensed under the GNU General Public License v3.0 (GPL-3.0).  
See the [LICENSE](LICENSE) file for details.


## References
1. Vicente-Serrano, S.M., Beguería, S., & López-Moreno, J.I. (2010). A multi-scalar drought index sensitive to global warming: The Standardized Precipitation Evapotranspiration Index. Journal of Climate, 23(7), 1696–1718. https://doi.org/10.1175/2009JCLI2909.1

2. McKee, T.B., Doesken, N.J., & Kleist, J. (1993). The relationship of drought frequency and duration to time scales. Proceedings of the 8th Conference on Applied Climatology, 179–184.


## Contact
For questions, suggestions, or collaborations, you can reach me at:

**Name:** Maria Cortès Simó

**Email:** mcortessimo@gmail.com