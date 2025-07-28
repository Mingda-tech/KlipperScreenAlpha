"""
AI Detection Manager
Main orchestrator for AI-based defect detection functionality
"""

import logging
import time
import threading
from typing import Optional, List, Dict, Any
from gi.repository import GLib

from .exceptions import AIDetectionError, AIServerConnectionError, CameraCaptureError
from .server_client import AIServerClient
from .camera_capture import AICameraCapture  
from .result_handler import DetectionResultHandler


class AIDetectionManager:
    """AI检测管理器"""
    
    def __init__(self, screen, config):
        self.screen = screen
        self.config = config
        self.is_monitoring = False
        self.detection_timer = None
        self._detection_thread = None
        self._should_stop = False
        self._last_health_check = 0
        self._health_check_interval = 60  # 每分钟检查一次健康状态
        self._error_count = 0
        self._max_errors = 5
        self._degraded_mode = False
        
        # 初始化组件
        try:
            self.ai_client = AIServerClient(config)
            self.camera = AICameraCapture(config)
            self.result_handler = DetectionResultHandler(screen, config)
            logging.info("AI检测管理器初始化成功")
        except Exception as e:
            logging.error(f"AI检测管理器初始化失败: {e}")
            raise AIDetectionError(f"初始化失败: {e}")
    
    def start_monitoring(self) -> bool:
        """开始AI监控"""
        try:
            # 检查AI服务是否启用
            if not self.config.get_ai_enabled():
                logging.info("AI服务未启用，无法开始监控")
                return False
            
            # 检查是否已在监控中
            if self.is_monitoring:
                logging.warning("AI监控已在运行中")
                return True
            
            # 健康检查
            if not self._perform_health_check():
                logging.error("AI服务器健康检查失败，无法开始监控")
                return False
            
            # 测试摄像头连接
            if not self.camera.test_camera_connection():
                logging.error("摄像头连接测试失败，无法开始监控")
                return False
            
            # 重置错误状态
            self._error_count = 0
            self._degraded_mode = False
            self._should_stop = False
            
            # 启动监控
            self.is_monitoring = True
            self._schedule_next_detection()
            
            logging.info("AI监控已启动")
            return True
            
        except Exception as e:
            logging.error(f"启动AI监控失败: {e}")
            return False
    
    def stop_monitoring(self) -> None:
        """停止AI监控"""
        try:
            if not self.is_monitoring:
                return
            
            self.is_monitoring = False
            self._should_stop = True
            
            # 取消定时器
            if self.detection_timer:
                GLib.source_remove(self.detection_timer)
                self.detection_timer = None
            
            # 等待检测线程结束
            if self._detection_thread and self._detection_thread.is_alive():
                self._detection_thread.join(timeout=5)
            
            logging.info("AI监控已停止")
            
        except Exception as e:
            logging.error(f"停止AI监控异常: {e}")
    
    def _schedule_next_detection(self) -> None:
        """调度下次检测"""
        if not self.is_monitoring or self._should_stop:
            return
        
        # 获取检测间隔
        interval = self.config.get_ai_detection_interval() * 1000  # 转换为毫秒
        
        # 在降级模式下延长检测间隔
        if self._degraded_mode:
            interval *= 2
        
        # 调度下次检测
        self.detection_timer = GLib.timeout_add(interval, self._perform_detection)
    
    def _perform_detection(self) -> bool:
        """执行单次检测"""
        if not self.is_monitoring or self._should_stop:
            return False
        
        try:
            # 检查是否应该执行检测
            if not self._should_perform_detection():
                self._schedule_next_detection()
                return False
            
            # 在后台线程中执行检测，避免阻塞UI
            self._detection_thread = threading.Thread(
                target=self._detection_worker,
                daemon=True
            )
            self._detection_thread.start()
            
            # 调度下次检测
            self._schedule_next_detection()
            return False  # 不重复当前定时器
            
        except Exception as e:
            logging.error(f"调度检测异常: {e}")
            self._handle_detection_failure(e)
            self._schedule_next_detection()
            return False
    
    def _should_perform_detection(self) -> bool:
        """判断是否应该执行检测"""
        try:
            # 检查打印状态
            printer_state = self.screen.printer.get_stat("print_stats", "state")
            if printer_state == "printing":
                return True
            elif printer_state == "paused":
                # 检查是否在暂停时继续检测
                return self.config.get_ai_detection_enabled_while_paused()
            else:
                # 其他状态（完成、取消、错误等）不执行检测
                return False
        
        except Exception as e:
            logging.error(f"检查打印状态异常: {e}")
            return False
    
    def _detection_worker(self) -> None:
        """检测工作线程"""
        try:
            # 定期健康检查
            current_time = time.time()
            if current_time - self._last_health_check > self._health_check_interval:
                if not self._perform_health_check():
                    raise AIServerConnectionError("AI服务器健康检查失败")
                self._last_health_check = current_time
            
            # 获取当前图像
            image_path = self.camera.capture_snapshot()
            if not image_path:
                raise CameraCaptureError("无法获取摄像头图像")
            
            # 执行AI检测
            result = self.ai_client.detect_sync(
                image_path=image_path,
                defect_types=self.config.get_enabled_defect_types(),
                task_id=f"monitor_{int(time.time())}"
            )
            
            # 在主线程中处理结果
            GLib.idle_add(self.result_handler.handle_detection_result, result)
            
            # 重置错误计数
            self._error_count = 0
            if self._degraded_mode:
                self._exit_degraded_mode()
            
        except Exception as e:
            logging.error(f"AI检测异常: {e}")
            GLib.idle_add(self._handle_detection_failure, e)
    
    def _perform_health_check(self) -> bool:
        """执行健康检查"""
        try:
            return self.ai_client.health_check()
        except Exception as e:
            logging.error(f"健康检查异常: {e}")
            return False
    
    def _handle_detection_failure(self, error: Exception, retry_count: int = 0) -> None:
        """处理检测失败"""
        self._error_count += 1
        
        # 记录错误
        GLib.idle_add(self.result_handler.handle_detection_error, error)
        
        # 如果错误次数过多，进入降级模式
        if self._error_count >= self._max_errors:
            self._enter_degraded_mode(error)
        
        logging.warning(f"检测失败 ({self._error_count}/{self._max_errors}): {error}")
    
    def _enter_degraded_mode(self, error: Exception) -> None:
        """进入降级运行模式"""
        if self._degraded_mode:
            return
        
        self._degraded_mode = True
        logging.warning(f"AI检测进入降级模式: {error}")
        
        # 显示降级通知
        message = "AI detection temporarily degraded due to errors"
        GLib.idle_add(self.screen.show_popup_message, message, 2)
        
        # 设置自动恢复检查（5分钟后）
        GLib.timeout_add(300000, self._try_recover_from_degraded_mode)
    
    def _exit_degraded_mode(self) -> None:
        """退出降级模式"""
        if not self._degraded_mode:
            return
        
        self._degraded_mode = False
        self._error_count = 0
        logging.info("AI检测已恢复正常模式")
        
        # 显示恢复通知
        message = "AI detection has recovered to normal operation"
        GLib.idle_add(self.screen.show_popup_message, message, 1)
    
    def _try_recover_from_degraded_mode(self) -> bool:
        """尝试从降级模式恢复"""
        if not self._degraded_mode:
            return False
        
        try:
            # 尝试健康检查
            if self._perform_health_check():
                # 尝试摄像头测试
                if self.camera.test_camera_connection():
                    self._exit_degraded_mode()
                    return False  # 停止重试定时器
            
            # 如果还是失败，继续在降级模式运行，10分钟后再试
            GLib.timeout_add(600000, self._try_recover_from_degraded_mode)
            return False
            
        except Exception as e:
            logging.error(f"降级模式恢复尝试失败: {e}")
            # 继续在降级模式，10分钟后再试
            GLib.timeout_add(600000, self._try_recover_from_degraded_mode)
            return False
    
    def manual_detection(self) -> Optional[Dict]:
        """手动执行一次检测"""
        try:
            if not self.config.get_ai_enabled():
                raise AIDetectionError("AI服务未启用")
            
            # 健康检查
            if not self.ai_client.health_check():
                raise AIServerConnectionError("AI服务器不可用")
            
            # 获取图像
            image_path = self.camera.capture_snapshot()
            if not image_path:
                raise CameraCaptureError("无法获取摄像头图像")
            
            # 执行检测
            result = self.ai_client.detect_sync(
                image_path=image_path,
                defect_types=self.config.get_enabled_defect_types(),
                task_id=f"manual_{int(time.time())}"
            )
            
            # 处理结果（但不触发自动暂停）
            self.result_handler._record_detection(result)
            
            return result
            
        except Exception as e:
            logging.error(f"手动检测失败: {e}")
            self.result_handler.handle_detection_error(e)
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        try:
            server_status = self.ai_client.get_server_status() if self.config.get_ai_enabled() else None
            detection_stats = self.result_handler.get_detection_stats()
            
            return {
                "monitoring": self.is_monitoring,
                "enabled": self.config.get_ai_enabled(),
                "degraded_mode": self._degraded_mode,
                "error_count": self._error_count,
                "server_healthy": self.ai_client.health_check() if self.config.get_ai_enabled() else False,
                "server_status": server_status,
                "camera_available": self.camera.test_camera_connection(),
                "detection_stats": detection_stats,
                "last_health_check": self._last_health_check,
                "config": {
                    "server_url": self.config.get_ai_server_url(),
                    "confidence_threshold": self.config.get_ai_confidence_threshold(),
                    "detection_interval": self.config.get_ai_detection_interval(),
                    "auto_pause": self.config.get_ai_auto_pause(),
                    "enabled_defect_types": self.config.get_enabled_defect_types(),
                    "camera_source": self.config.get_camera_source()
                }
            }
        except Exception as e:
            logging.error(f"获取状态异常: {e}")
            return {
                "monitoring": self.is_monitoring,
                "enabled": False,
                "error": str(e)
            }
    
    def on_printer_state_changed(self, state: str) -> None:
        """打印状态变化处理"""
        try:
            logging.debug(f"打印状态变化: {state}")
            
            if state == "printing":
                # 开始打印时自动启动监控
                if self.config.get_ai_enabled() and not self.is_monitoring:
                    self.start_monitoring()
            elif state in ["complete", "cancelled", "error"]:
                # 打印结束时停止监控
                if self.is_monitoring:
                    self.stop_monitoring()
            elif state == "paused":
                # 打印暂停时根据配置决定是否继续监控
                if not self.config.get_ai_detection_enabled_while_paused():
                    if self.is_monitoring:
                        self.stop_monitoring()
            
        except Exception as e:
            logging.error(f"处理打印状态变化异常: {e}")
    
    def update_config(self, config) -> None:
        """更新配置"""
        try:
            self.config = config
            
            # 更新AI客户端配置
            self.ai_client.update_base_url(config.get_ai_server_url())
            
            # 如果AI服务被禁用，停止监控
            if not config.get_ai_enabled() and self.is_monitoring:
                self.stop_monitoring()
            
            logging.info("AI检测管理器配置已更新")
            
        except Exception as e:
            logging.error(f"更新配置异常: {e}")
    
    def get_detection_history(self, limit: int = 20) -> List[Dict]:
        """获取检测历史"""
        return self.result_handler.get_detection_history(limit)
    
    def clear_detection_history(self) -> None:
        """清除检测历史"""
        self.result_handler.clear_history()
    
    def export_detection_history(self, filepath: str) -> bool:
        """导出检测历史"""
        return self.result_handler.export_history(filepath)
    
    def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        result = {
            "server_connection": False,
            "camera_connection": False,
            "server_status": None,
            "error_messages": []
        }
        
        try:
            # 测试AI服务器连接
            if self.ai_client.health_check():
                result["server_connection"] = True
                result["server_status"] = self.ai_client.get_server_status()
            else:
                result["error_messages"].append("AI服务器健康检查失败")
            
        except Exception as e:
            result["error_messages"].append(f"AI服务器连接错误: {e}")
        
        try:
            # 测试摄像头连接
            if self.camera.test_camera_connection():
                result["camera_connection"] = True
            else:
                result["error_messages"].append("摄像头连接测试失败")
                
        except Exception as e:
            result["error_messages"].append(f"摄像头连接错误: {e}")
        
        return result
    
    def cleanup(self) -> None:
        """清理资源"""
        try:
            # 停止监控
            self.stop_monitoring()
            
            # 关闭AI客户端连接
            if hasattr(self, 'ai_client'):
                self.ai_client.close()
            
            logging.info("AI检测管理器资源已清理")
            
        except Exception as e:
            logging.error(f"清理资源异常: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()