import logging
import time


class LogfmtFormatter(logging.Formatter):
    def mask_value(self, value: str, visible_start: int, visible_end: int, mask_char: str = "*"):
        return value[:visible_start] + mask_char * (len(value) - visible_start - visible_end) + value[-visible_end:]

    def format(self, record: logging.LogRecord):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
        log_parts = [
            f"ts=\"{timestamp}\"",
            f"level=\"{record.levelname.lower()}\"",
            f"msg=\"{record.getMessage()}\"",
            f"module=\"{record.module}\"",
            f"func=\"{record.funcName}\"",
            f"line=\"{record.lineno}\""
        ]

        for key, value in record.__dict__.items():
            if key not in (
                    "msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text",
                    "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName",
                    "process", "processName", "taskName"):
                # Masking sensitive data in case of log leak
                # Can be extended to multiple values
                if key == "app_secret":
                    value = self.mask_value(value, visible_start=4, visible_end=4)
                log_parts.append(f"{key}=\"{value}\"")

        return " ".join(log_parts)


def setup_logger(level=logging.DEBUG):
    logger = logging.getLogger("structurebot")

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(LogfmtFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger


logger = logging.getLogger("structurebot")
