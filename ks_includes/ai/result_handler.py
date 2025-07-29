"""
Detection Result Handler
Processes AI detection results and handles user notifications and actions
"""

import time
import logging
from typing import Dict, List, Optional, Any
from gi.repository import GLib

from .exceptions import AIDetectionError


class DetectionResultHandler:
    """检测结果处理器"""
    
    def __init__(self, screen, config):
        self.screen = screen
        self.config = config
        self.detection_history: List[Dict] = []
        self._last_detection_time = 0
        self._consecutive_detections = 0
        self._last_defect_type = None
    
    def handle_detection_result(self, result: Dict) -> None:
        """处理检测结果"""
        try:
            # 记录检测历史
            self._record_detection(result)
            
            # 更新最后检测时间
            self._last_detection_time = time.time()
            
            # 检查是否检测到缺陷
            if result.get("has_defect", False):
                self._handle_defect_detected(result)
            else:
                self._handle_no_defect_detected(result)
                
        except Exception as e:
            logging.error(f"处理检测结果异常: {e}")
            self.handle_detection_error(e)
    
    def _handle_defect_detected(self, result: Dict) -> None:
        """处理检测到缺陷的情况"""
        detections = result.get("detections", [])
        if not detections:
            logging.warning("检测结果显示有缺陷但没有具体检测信息")
            return
        
        # 获取最高置信度的检测结果
        max_detection = max(detections, key=lambda x: x.get("confidence", 0))
        confidence = max_detection.get("confidence", 0)
        defect_type = max_detection.get("class_name", "unknown")
        
        # 检查是否超过置信度阈值
        threshold = self.config.get_ai_confidence_threshold() / 100.0
        if confidence >= threshold:
            logging.warning(f"检测到缺陷: {defect_type}, 置信度: {confidence:.2f}")
            
            # 更新连续检测计数
            if defect_type == self._last_defect_type:
                self._consecutive_detections += 1
            else:
                self._consecutive_detections = 1
                self._last_defect_type = defect_type
            
            # 决定后续动作
            if self._should_auto_pause(defect_type, confidence):
                self._auto_pause_print(defect_type, confidence, result)
            else:
                self._show_defect_warning(defect_type, confidence, result)
        else:
            logging.info(f"检测到缺陷但置信度低于阈值: {defect_type}, 置信度: {confidence:.2f}")
            self._reset_consecutive_detections()
    
    def _handle_no_defect_detected(self, result: Dict) -> None:
        """处理未检测到缺陷的情况"""
        logging.debug("AI检测正常，未发现缺陷")
        self._reset_consecutive_detections()
        
        # 可选：更新UI状态显示
        self._update_status_display("normal", result)
    
    def _should_auto_pause(self, defect_type: str, confidence: float) -> bool:
        """判断是否应该自动暂停"""
        auto_pause_enabled = self.config.get_ai_auto_pause()
        logging.debug(f"AI自动暂停配置: {auto_pause_enabled}")
        
        if not auto_pause_enabled:
            logging.info("AI自动暂停未启用，仅显示警告")
            return False
        
        # 检查打印机状态
        printer_state = self.screen.printer.get_stat("print_stats", "state")
        logging.debug(f"打印机当前状态: {printer_state}")
        if printer_state != "printing":
            logging.info(f"打印机未在打印状态({printer_state})，不执行自动暂停")
            return False
        
        threshold = self.config.get_ai_confidence_threshold() / 100.0
        should_pause = confidence >= threshold
        
        logging.info(f"自动暂停判断: 缺陷={defect_type}, 置信度={confidence:.2%}, 阈值={self.config.get_ai_confidence_threshold()}%, 是否暂停={should_pause}")
        return should_pause
    
    def _auto_pause_print(self, defect_type: str, confidence: float, result: Dict) -> None:
        """自动暂停打印"""
        try:
            # 播放通知声音（如果启用）
            if self.config.get_ai_notification_sound():
                self._play_notification_sound()
            
            # 暂停打印
            self.screen._ws.klippy.print_pause()
            
            # 显示AI暂停面板
            extra_data = {
                "defect_type": defect_type,
                "confidence": confidence,
                "auto_paused": True,
                "detection_result": result,
                "detection_time": time.time()
            }
            
            # 使用GLib.idle_add确保在主线程中更新UI
            GLib.idle_add(
                self.screen.show_panel,
                "ai_pause",
                "AI Detection Alert",
                extra_data
            )
            
            logging.info(f"因检测到{defect_type}缺陷自动暂停打印，置信度: {confidence:.2%}")
            
        except Exception as e:
            logging.error(f"自动暂停打印失败: {e}")
            # 如果暂停失败，至少显示警告
            self._show_defect_warning(defect_type, confidence, result)
    
    def _show_defect_warning(self, defect_type: str, confidence: float, result: Dict) -> None:
        """显示缺陷警告"""
        message = f"Detected defect: {defect_type} (Confidence: {confidence:.1%})"
        
        # 播放通知声音（如果启用）
        if self.config.get_ai_notification_sound():
            self._play_notification_sound()
        
        # 显示通知消息
        GLib.idle_add(
            self.screen.show_popup_message,
            message,
            2  # 警告级别
        )
        
        # 更新状态显示
        self._update_status_display("warning", result, defect_type, confidence)
        
        logging.warning(f"显示缺陷警告: {message}")
    
    def _record_detection(self, result: Dict) -> None:
        """记录检测历史"""
        detection_record = {
            "timestamp": time.time(),
            "task_id": result.get("task_id"),
            "has_defect": result.get("has_defect", False),
            "detections": result.get("detections", []),
            "inference_time": result.get("inference_time", 0),
            "model_name": result.get("model_name"),
            "confidence": self._get_max_confidence(result),
            "defect_type": self._get_primary_defect_type(result)
        }
        
        self.detection_history.append(detection_record)
        
        # 限制历史记录数量
        max_history = 100
        if len(self.detection_history) > max_history:
            self.detection_history = self.detection_history[-max_history:]
    
    def _get_max_confidence(self, result: Dict) -> float:
        """获取最高置信度"""
        detections = result.get("detections", [])
        if not detections:
            return 0.0
        return max(detection.get("confidence", 0) for detection in detections)
    
    def _get_primary_defect_type(self, result: Dict) -> Optional[str]:
        """获取主要缺陷类型"""
        detections = result.get("detections", [])
        if not detections:
            return None
        
        max_detection = max(detections, key=lambda x: x.get("confidence", 0))
        return max_detection.get("class_name")
    
    def _reset_consecutive_detections(self) -> None:
        """重置连续检测计数"""
        self._consecutive_detections = 0
        self._last_defect_type = None
    
    def _play_notification_sound(self) -> None:
        """播放通知声音"""
        try:
            # 尝试播放系统通知声音
            import subprocess
            subprocess.run(['paplay', '/usr/share/sounds/alsa/Front_Right.wav'], 
                         check=False, timeout=1)
        except Exception as e:
            logging.debug(f"播放通知声音失败: {e}")
    
    def _update_status_display(self, status: str, result: Dict, 
                              defect_type: Optional[str] = None, 
                              confidence: Optional[float] = None) -> None:
        """更新状态显示"""
        try:
            # 如果主屏幕有AI状态更新方法，调用它
            if hasattr(self.screen, 'update_ai_status'):
                GLib.idle_add(
                    self.screen.update_ai_status,
                    status, defect_type, confidence, result
                )
        except Exception as e:
            logging.debug(f"更新状态显示失败: {e}")
    
    def handle_detection_error(self, error: Exception) -> None:
        """处理检测错误"""
        logging.error(f"AI检测错误: {error}")
        
        # 显示错误通知
        error_message = f"AI Detection Error: {str(error)}"
        GLib.idle_add(
            self.screen.show_popup_message,
            error_message,
            3  # 错误级别
        )
        
        # 记录错误到历史
        error_record = {
            "timestamp": time.time(),
            "error": str(error),
            "error_type": type(error).__name__,
            "type": "detection_error"
        }
        self.detection_history.append(error_record)
        
        # 重置连续检测状态
        self._reset_consecutive_detections()
    
    def get_detection_history(self, limit: int = 20) -> List[Dict]:
        """获取检测历史"""
        return self.detection_history[-limit:] if limit > 0 else self.detection_history
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """获取检测统计信息"""
        if not self.detection_history:
            return {
                "total_detections": 0,
                "defect_detections": 0,
                "defect_rate": 0.0,
                "avg_inference_time": 0.0,
                "last_detection_time": None
            }
        
        # 过滤出有效的检测记录（排除错误记录）
        valid_detections = [
            record for record in self.detection_history 
            if record.get("type") != "detection_error"
        ]
        
        if not valid_detections:
            return {
                "total_detections": 0,
                "defect_detections": 0,
                "defect_rate": 0.0,
                "avg_inference_time": 0.0,
                "last_detection_time": None
            }
        
        defect_detections = [
            record for record in valid_detections
            if record.get("has_defect", False)
        ]
        
        # 计算平均推理时间
        inference_times = [
            record.get("inference_time", 0) 
            for record in valid_detections
            if record.get("inference_time", 0) > 0
        ]
        avg_inference_time = sum(inference_times) / len(inference_times) if inference_times else 0.0
        
        # 最后检测时间
        last_detection_time = max(
            record.get("timestamp", 0) for record in valid_detections
        ) if valid_detections else None
        
        return {
            "total_detections": len(valid_detections),
            "defect_detections": len(defect_detections),
            "defect_rate": len(defect_detections) / len(valid_detections) * 100,
            "avg_inference_time": avg_inference_time,
            "last_detection_time": last_detection_time,
            "consecutive_detections": self._consecutive_detections,
            "current_defect_type": self._last_defect_type
        }
    
    def clear_history(self) -> None:
        """清除检测历史"""
        self.detection_history.clear()
        self._reset_consecutive_detections()
        logging.info("AI检测历史已清除")
    
    def export_history(self, filepath: str) -> bool:
        """导出检测历史到文件"""
        try:
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "export_time": time.time(),
                    "history": self.detection_history,
                    "stats": self.get_detection_stats()
                }, f, indent=2, ensure_ascii=False)
            
            logging.info(f"检测历史已导出到: {filepath}")
            return True
            
        except Exception as e:
            logging.error(f"导出检测历史失败: {e}")
            return False