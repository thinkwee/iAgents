import logging
import os
import yaml
from datetime import datetime
import csv

# Load global config with error handling
file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
config_path = os.path.join(project_path, "config/global.yaml")

try:
    with open(config_path, "r") as config_file:
        global_config = yaml.safe_load(config_file)
except FileNotFoundError:
    raise Exception(f"Configuration file not found: {config_path}")
except yaml.YAMLError as e:
    raise Exception(f"Error parsing YAML file: {config_path}\n{e}")


class iAgentsLogger:
    """Logger class for handling structured logging to CSV files."""

    logger = None  # Class variable for the logger instance
    writer = None  # Class variable for the CSV writer

    @classmethod
    def set_logger(cls, logger):
        """Sets the logger instance for logging plain text."""
        if not hasattr(logger, 'info'):
            raise ValueError("Logger must have an 'info' method.")
        cls.logger = logger

    @classmethod
    def set_evaluate_log_path(cls, exp_name, file_prefix):
        """Sets the path for the evaluation log file and initializes the CSV writer."""
        log_dir = os.path.join(project_path, "exp", exp_name)
        os.makedirs(log_dir, exist_ok=True)
        csv_log_path = os.path.join(
            log_dir, global_config.get('logging', {}).get('logname', 'default') + f"_{file_prefix}_llm.csv"
        )
        cls._initialize_writer(csv_log_path, ['timestamp', 'instruction/none-llm operation', 'query', 'response'])

    @classmethod
    def set_log_path(cls, file_timestamp):
        """Sets the path for the general log file and initializes the CSV writer."""
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        csv_log_path = os.path.join(
            log_dir, global_config.get('logging', {}).get('logname', 'default') + f"_{file_timestamp}_llm.csv"
        )
        cls._initialize_writer(csv_log_path, ['timestamp', 'instruction', 'query', 'response'])

    @classmethod
    def _initialize_writer(cls, csv_log_path, header):
        """Initializes the CSV writer with the given log path and header."""
        try:
            if os.path.exists(csv_log_path):
                cls.writer = csv.writer(open(csv_log_path, "a", newline=''))
            else:
                cls.writer = csv.writer(open(csv_log_path, "w", newline=''))
                cls.writer.writerow(header)
        except IOError as e:
            raise Exception(f"Failed to open or write to log file: {csv_log_path}\n{e}")

    @classmethod
    def log(cls, query=None, response=None, instruction=None):
        """Logs the given information to the CSV and the plain text logger."""
        if cls.writer is None:
            raise ValueError("CSV writer is not initialized. Call 'set_log_path' or 'set_evaluate_log_path' first.")

        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        instruction = instruction or "None"
        query = query or "None"
        response = response or "None"

        # Write to CSV
        cls.writer.writerow([current_timestamp, instruction, query, response])

        # Prepare the detailed log message
        detailed_log = f"{instruction}\n>>>>>>>> Input >>>>>>>>:\n{query}\n<<<<<<<< Output <<<<<<<<:\n{response}\n"

        # Write to plain text logger
        if cls.logger:
            cls.logger.info(detailed_log)
        else:
            logging.info(detailed_log)
