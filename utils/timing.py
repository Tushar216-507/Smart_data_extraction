import time
import functools
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pipeline_tracer")

def time_stage(stage_name: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger.info(f"Starting stage: {stage_name}")
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                logger.info(f"Finished stage: {stage_name} in {duration:.2f} seconds")
        return wrapper
    return decorator
