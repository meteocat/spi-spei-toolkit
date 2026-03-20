""" Plotting functions for point-based SPEI/SPI index """
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def plot_index_point(index_name: str, data: pd.Series, index_type: int,
                     station_code: str, figsize: tuple = (12, 4), save_path: str = None):
    """
    Plot the time series of a point-based SPEI or SPI index.

    Args:
        index_name (str): 'SPEI' or 'SPI'.
        data (pd.Series): Time series with datetime index.
        index_type (int): Index accumulation period (in months).
        station_code (str): Station code.
        figsize (tuple, optional): Figure size (width, height). Default (12, 4).
        save_path (str, optional): Path to save the figure. If None, figure is only shown.

    Returns:
        fig, ax : Matplotlib Figure and Axes objects for further customization.
    """
    # Keep only finite values
    data = data[np.isfinite(data)]
    
    fig, ax = plt.subplots(figsize=figsize)
    x = data.index
    y = data.values

    # Fill positive and negative values
    ax.fill_between(x, y, 0, where=y >= 0, color='blue', alpha=0.5)
    ax.fill_between(x, y, 0, where=y <= 0, color='red', alpha=0.5)

    # Plot line
    ax.plot(x, y, color='black', linewidth=0.8)

    # Y-axis limits
    lim = max(round(np.nanmax(np.abs(y)), 0), 3)
    ax.set_ylim(-lim, lim)
    ax.set_yticks(np.arange(-lim, lim + 0.1, 1))

    # Horizontal line at 0
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)

    # Grid, labels and title
    ax.grid(True, alpha=0.2)
    ax.set_xlabel('Date')
    ax.set_ylabel(index_name)
    ax.set_title(f'{index_name} - {index_type} months, {station_code}', fontsize=15)

    # Format x-axis dates
    fig.autofmt_xdate()
    plt.tight_layout()

    # Save figure if path provided
    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    return fig, ax