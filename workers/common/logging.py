import logging
import sys


def configure_logging(worker_name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s [{worker_name}] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger(worker_name)
