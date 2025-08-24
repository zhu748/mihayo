import logging
import platform
import sys
import re
from typing import Dict, Optional
from app.utils.helpers import redact_key_for_logging as _redact_key_for_logging

# ANSI转义序列颜色代码
COLORS = {
    "DEBUG": "\033[34m",  # 蓝色
    "INFO": "\033[32m",  # 绿色
    "WARNING": "\033[33m",  # 黄色
    "ERROR": "\033[31m",  # 红色
    "CRITICAL": "\033[1;31m",  # 红色加粗
}



# Windows系统启用ANSI支持
if platform.system() == "Windows":
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


class ColoredFormatter(logging.Formatter):
    """
    自定义的日志格式化器,添加颜色支持
    """

    def format(self, record):
        # 获取对应级别的颜色代码
        color = COLORS.get(record.levelname, "")
        # 添加颜色代码和重置代码
        record.levelname = f"{color}{record.levelname}\033[0m"
        # 创建包含文件名和行号的固定宽度字符串
        record.fileloc = f"[{record.filename}:{record.lineno}]"
        return super().format(record)


class AccessLogFormatter(logging.Formatter):
    """
    Custom access log formatter that redacts API keys in URLs
    """

    # API key patterns to match in URLs
    API_KEY_PATTERNS = [
        r'\bAIza[0-9A-Za-z_-]{35}',  # Google API keys (like Gemini)
        r'\bsk-[0-9A-Za-z_-]{20,}',  # OpenAI and general sk- prefixed keys
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Compile regex patterns for better performance
        self.compiled_patterns = [re.compile(pattern) for pattern in self.API_KEY_PATTERNS]

    def format(self, record):
        # Format the record normally first
        formatted_msg = super().format(record)

        # Redact API keys in the formatted message
        return self._redact_api_keys_in_message(formatted_msg)

    def _redact_api_keys_in_message(self, message: str) -> str:
        """
        Replace API keys in log message with redacted versions
        """
        try:
            for pattern in self.compiled_patterns:
                def replace_key(match):
                    key = match.group(0)
                    return _redact_key_for_logging(key)

                message = pattern.sub(replace_key, message)

            return message
        except Exception as e:
            # Log the error but don't expose the original message in case it contains keys
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error redacting API keys in access log: {e}")
            return "[LOG_REDACTION_ERROR]"


# 日志格式 - 使用 fileloc 并设置固定宽度 (例如 30)
FORMATTER = ColoredFormatter(
    "%(asctime)s | %(levelname)-17s | %(fileloc)-30s | %(message)s"
)

# 日志级别映射
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


class Logger:
    def __init__(self):
        pass

    _loggers: Dict[str, logging.Logger] = {}

    @staticmethod
    def setup_logger(name: str) -> logging.Logger:
        """
        设置并获取logger
        :param name: logger名称
        :return: logger实例
        """
        # 导入 settings 对象
        from app.config.config import settings

        # 从全局配置获取日志级别
        log_level_str = settings.LOG_LEVEL.lower()
        level = LOG_LEVELS.get(log_level_str, logging.INFO)

        if name in Logger._loggers:
            # 如果 logger 已存在，检查并更新其级别（如果需要）
            existing_logger = Logger._loggers[name]
            if existing_logger.level != level:
                existing_logger.setLevel(level)
            return existing_logger

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        # 添加控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(FORMATTER)
        logger.addHandler(console_handler)

        Logger._loggers[name] = logger
        return logger

    @staticmethod
    def get_logger(name: str) -> Optional[logging.Logger]:
        """
        获取已存在的logger
        :param name: logger名称
        :return: logger实例或None
        """
        return Logger._loggers.get(name)

    @staticmethod
    def update_log_levels(log_level: str):
        """
        根据当前的全局配置更新所有已创建 logger 的日志级别。
        """
        log_level_str = log_level.lower()
        new_level = LOG_LEVELS.get(log_level_str, logging.INFO)

        updated_count = 0
        for logger_name, logger_instance in Logger._loggers.items():
            if logger_instance.level != new_level:
                logger_instance.setLevel(new_level)
                # 可选：记录级别变更日志，但注意避免在日志模块内部产生过多日志
                # print(f"Updated log level for logger '{logger_name}' to {log_level_str.upper()}")
                updated_count += 1


# 预定义的loggers
def get_openai_logger():
    return Logger.setup_logger("openai")


def get_gemini_logger():
    return Logger.setup_logger("gemini")


def get_chat_logger():
    return Logger.setup_logger("chat")


def get_model_logger():
    return Logger.setup_logger("model")


def get_security_logger():
    return Logger.setup_logger("security")


def get_key_manager_logger():
    return Logger.setup_logger("key_manager")


def get_main_logger():
    return Logger.setup_logger("main")


def get_embeddings_logger():
    return Logger.setup_logger("embeddings")


def get_request_logger():
    return Logger.setup_logger("request")


def get_retry_logger():
    return Logger.setup_logger("retry")


def get_image_create_logger():
    return Logger.setup_logger("image_create")


def get_exceptions_logger():
    return Logger.setup_logger("exceptions")


def get_application_logger():
    return Logger.setup_logger("application")


def get_initialization_logger():
    return Logger.setup_logger("initialization")


def get_middleware_logger():
    return Logger.setup_logger("middleware")


def get_routes_logger():
    return Logger.setup_logger("routes")


def get_config_routes_logger():
    return Logger.setup_logger("config_routes")


def get_config_logger():
    return Logger.setup_logger("config")


def get_database_logger():
    return Logger.setup_logger("database")


def get_log_routes_logger():
    return Logger.setup_logger("log_routes")


def get_stats_logger():
    return Logger.setup_logger("stats")


def get_update_logger():
    return Logger.setup_logger("update_service")


def get_scheduler_routes():
    return Logger.setup_logger("scheduler_routes")


def get_message_converter_logger():
    return Logger.setup_logger("message_converter")


def get_api_client_logger():
    return Logger.setup_logger("api_client")


def get_openai_compatible_logger():
    return Logger.setup_logger("openai_compatible")


def get_error_log_logger():
    return Logger.setup_logger("error_log")


def get_request_log_logger():
    return Logger.setup_logger("request_log")


def get_files_logger():
    return Logger.setup_logger("files")


def get_vertex_express_logger():
    return Logger.setup_logger("vertex_express")


def get_gemini_embedding_logger():
    return Logger.setup_logger("gemini_embedding")


def setup_access_logging():
    """
    Configure uvicorn access logging with API key redaction

    This function sets up a custom access log formatter that automatically
    redacts API keys in HTTP access logs. It works by:

    1. Intercepting uvicorn's access log messages
    2. Using regex patterns to find API keys in URLs
    3. Replacing them with redacted versions (first6...last6)

    Supported API key formats:
    - Google/Gemini API keys: AIza[35 chars]
    - OpenAI API keys: sk-[48 chars]
    - General sk- prefixed keys: sk-[20+ chars]

    Usage:
    - Automatically called in main.py when running with uvicorn
    - For production deployment with gunicorn, ensure this is called in startup
    """
    # Get the uvicorn access logger
    access_logger = logging.getLogger("uvicorn.access")

    # Remove existing handlers to avoid duplicate logs
    for handler in access_logger.handlers[:]:
        access_logger.removeHandler(handler)

    # Create new handler with our custom formatter that includes timestamp and log level
    handler = logging.StreamHandler(sys.stdout)
    access_formatter = AccessLogFormatter("%(asctime)s | %(levelname)-8s | %(message)s")
    handler.setFormatter(access_formatter)

    # Add the handler to uvicorn access logger
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    return access_logger

