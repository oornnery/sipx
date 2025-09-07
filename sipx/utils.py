import logging
from rich.logging import RichHandler

# Define the log message format
FORMAT = "%(message)s"

# Configure the basic logging setup
logging.basicConfig(
    level="NOTSET",  # Set the lowest level to capture all messages
    format=FORMAT,
    datefmt="[%X]",  # Format for the timestamp
    handlers=[RichHandler()] # Use RichHandler for colorful output
)

# Get a logger instance
log = logging.getLogger("rich")

# Log various messages at different levels
log.debug("This is a debug message.")
log.info("This is an informational message.")
log.warning("This is a warning message.")
log.error("This is an error message.")
log.critical("This is a critical message!")
