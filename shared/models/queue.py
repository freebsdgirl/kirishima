# Queue/task data models removed per deprecation of internal queue system.
from shared.log_config import get_logger
logger = get_logger("proxy.shared.models.queue")
logger.info("shared.models.queue imported after deprecation; all classes removed.")

__all__ = []