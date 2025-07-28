"""
AI Server Client
Handles communication with the AI detection server
"""

import logging
import requests
import time
from typing import Dict, List, Optional, Union

from .exceptions import AIServerConnectionError, DetectionTimeoutError, AIDetectionError


class AIServerClient:
    """AI服务器客户端"""
    
    def __init__(self, config):
        self.config = config
        self.base_url = config.get_ai_server_url()
        self.timeout = 30
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'KlipperScreen-AI/1.0'
        })
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/health",
                timeout=5
            )
            response.raise_for_status()
            result = response.json()
            return result.get("success", False) and result.get("status") == "healthy"
        except requests.exceptions.RequestException as e:
            logging.error(f"AI服务器健康检查失败: {e}")
            return False
        except Exception as e:
            logging.error(f"健康检查异常: {e}")
            return False
    
    def detect_sync(self, image_path: str, defect_types: Optional[List[str]] = None, 
                   task_id: Optional[str] = None) -> Dict:
        """同步检测"""
        try:
            # 构建请求数据
            request_data = {
                "image_source": {
                    "type": "local_path",
                    "value": image_path
                },
                "task_id": task_id or f"detect_{int(time.time())}"
            }
            
            # 如果指定了缺陷类型
            if defect_types:
                if len(defect_types) == 1:
                    request_data["defect_type"] = defect_types[0]
                # 多类型检测时不指定defect_type，让服务器检测所有类型
            
            # 发送请求
            response = self.session.post(
                f"{self.base_url}/api/v1/detect",
                json=request_data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("success"):
                raise AIDetectionError(f"检测失败: {result.get('message', 'Unknown error')}")
            
            return result
            
        except requests.exceptions.Timeout:
            raise DetectionTimeoutError("检测请求超时")
        except requests.exceptions.ConnectionError as e:
            raise AIServerConnectionError(f"连接AI服务器失败: {e}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise AIServerConnectionError("AI服务器检测接口不存在")
            elif e.response.status_code == 500:
                raise AIDetectionError("AI服务器内部错误")
            else:
                raise AIServerConnectionError(f"HTTP错误: {e.response.status_code}")
        except requests.exceptions.RequestException as e:
            raise AIServerConnectionError(f"网络请求失败: {e}")
        except ValueError as e:
            raise AIDetectionError(f"响应解析失败: {e}")
        except Exception as e:
            raise AIDetectionError(f"检测过程出现未知错误: {e}")
    
    def detect_async(self, image_path: str, defect_types: Optional[List[str]] = None,
                    task_id: Optional[str] = None, callback_url: Optional[str] = None) -> Dict:
        """异步检测"""
        try:
            request_data = {
                "image_source": {
                    "type": "local_path", 
                    "value": image_path
                },
                "task_id": task_id or f"async_{int(time.time())}"
            }
            
            if defect_types and len(defect_types) == 1:
                request_data["defect_type"] = defect_types[0]
            
            if callback_url:
                request_data["callback_url"] = callback_url
            
            response = self.session.post(
                f"{self.base_url}/api/v1/detect/async",
                json=request_data,
                timeout=10  # 异步请求超时时间短一些
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("success"):
                raise AIDetectionError(f"异步检测提交失败: {result.get('message')}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise AIServerConnectionError(f"异步检测请求失败: {e}")
        except ValueError as e:
            raise AIDetectionError(f"异步检测响应解析失败: {e}")
    
    def get_server_status(self) -> Optional[Dict]:
        """获取服务器状态"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/status",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"获取服务器状态失败: {e}")
            return None
    
    def get_detection_result(self, task_id: str) -> Optional[Dict]:
        """获取异步检测结果（如果服务器支持）"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/detect/result/{task_id}",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None  # 结果不存在或已过期
            raise
        except Exception as e:
            logging.error(f"获取检测结果失败: {e}")
            return None
    
    def update_base_url(self, new_url: str):
        """更新服务器地址"""
        self.base_url = new_url.rstrip('/')
        logging.info(f"AI服务器地址已更新为: {self.base_url}")
    
    def close(self):
        """关闭会话"""
        if self.session:
            self.session.close()
    
    def __del__(self):
        """析构函数"""
        self.close()