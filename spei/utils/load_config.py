"""Module to import configuration files.
"""
import json
from os.path import exists


def load_config(config_file):
    """Load configuration .json file.

    Args:
        config_file (str): Path to a configuration file in .json format.

    Raises:
        FileNotFoundError: If configuration file is not found.

    Returns:
        dict: Configuration dictionary.
    """
    if not exists(config_file):
        raise FileNotFoundError(config_file + " does not exist.")

    with open(config_file, "rb") as c_f:
        config = json.load(c_f)
        c_f.close()

    return config
