"""
AI Detection Exception Classes
Defines custom exceptions for AI detection functionality
"""


class AIDetectionError(Exception):
    """AI检测相关异常基类"""
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class AIServerConnectionError(AIDetectionError):
    """AI服务器连接异常"""
    pass


class CameraCaptureError(AIDetectionError):
    """摄像头采集异常"""
    pass


class DetectionTimeoutError(AIDetectionError):
    """检测超时异常"""
    pass


class InvalidConfigurationError(AIDetectionError):
    """配置无效异常"""
    pass


class ModelLoadError(AIDetectionError):
    """模型加载异常"""
    pass