"""
AI Camera Capture
Handles image capture from various sources for AI detection
"""

import os
import time
import glob
import logging
import requests
from typing import Optional, List, Dict

from .exceptions import CameraCaptureError


class AICameraCapture:
    """AI摄像头图像采集器"""
    
    def __init__(self, config):
        self.config = config
        self.temp_dir = "/tmp/klipperscreen_ai"
        self._ensure_temp_dir()
    
    def _ensure_temp_dir(self):
        """确保临时目录存在"""
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"创建临时目录失败: {e}")
            # 使用备用目录
            self.temp_dir = "/tmp"
    
    def capture_snapshot(self) -> Optional[str]:
        """获取当前快照"""
        source = self.config.get_camera_source()
        
        try:
            if source == "moonraker":
                return self._capture_from_moonraker()
            elif source == "local":
                return self._capture_from_local()
            elif source == "url":
                return self._capture_from_url()
            else:
                raise CameraCaptureError(f"不支持的摄像头源: {source}")
        except Exception as e:
            logging.error(f"图像采集失败: {e}")
            return None
    
    def _capture_from_moonraker(self) -> Optional[str]:
        """从Moonraker获取摄像头快照"""
        try:
            # 获取摄像头配置
            cameras = self._get_moonraker_cameras()
            if not cameras:
                logging.warning("未找到可用的Moonraker摄像头")
                return None
            
            # 使用第一个可用摄像头
            camera = cameras[0]
            snapshot_url = self._build_snapshot_url(camera)
            
            # 下载图像
            response = requests.get(snapshot_url, timeout=10)
            response.raise_for_status()
            
            # 检查响应内容类型
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise CameraCaptureError(f"无效的图像内容类型: {content_type}")
            
            # 保存到临时文件
            return self._save_image_data(response.content, "moonraker")
            
        except requests.exceptions.RequestException as e:
            raise CameraCaptureError(f"从Moonraker获取图像失败: {e}")
        except Exception as e:
            raise CameraCaptureError(f"Moonraker图像采集异常: {e}")
    
    def _capture_from_local(self) -> Optional[str]:
        """从本地摄像头获取图像"""
        try:
            # 尝试使用OpenCV (如果可用)
            try:
                import cv2
                return self._capture_with_opencv()
            except ImportError:
                logging.warning("OpenCV不可用，尝试使用其他方法")
            
            # 尝试使用fswebcam (Linux)
            if os.path.exists('/usr/bin/fswebcam'):
                return self._capture_with_fswebcam()
            
            # 尝试使用v4l2 (Video4Linux2)
            return self._capture_with_v4l2()
            
        except Exception as e:
            raise CameraCaptureError(f"本地摄像头采集失败: {e}")
    
    def _capture_from_url(self) -> Optional[str]:
        """从URL获取图像"""
        try:
            camera_url = self.config.get_camera_url()
            if not camera_url:
                raise CameraCaptureError("未配置摄像头URL")
            
            response = requests.get(camera_url, timeout=10)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise CameraCaptureError(f"URL返回的不是图像内容: {content_type}")
            
            return self._save_image_data(response.content, "url")
            
        except requests.exceptions.RequestException as e:
            raise CameraCaptureError(f"从URL获取图像失败: {e}")
    
    def _capture_with_opencv(self) -> Optional[str]:
        """使用OpenCV采集图像"""
        import cv2
        
        # 尝试打开默认摄像头
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            raise CameraCaptureError("无法打开摄像头设备")
        
        try:
            # 设置分辨率
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # 捕获帧
            ret, frame = cap.read()
            if not ret:
                raise CameraCaptureError("无法从摄像头读取图像")
            
            # 保存图像
            timestamp = int(time.time())
            temp_path = os.path.join(self.temp_dir, f"opencv_{timestamp}.jpg")
            
            success = cv2.imwrite(temp_path, frame)
            if not success:
                raise CameraCaptureError("保存OpenCV图像失败")
            
            return temp_path
            
        finally:
            cap.release()
    
    def _capture_with_fswebcam(self) -> Optional[str]:
        """使用fswebcam采集图像"""
        timestamp = int(time.time())
        temp_path = os.path.join(self.temp_dir, f"fswebcam_{timestamp}.jpg")
        
        # 构建fswebcam命令
        cmd = f"fswebcam -r 640x480 --no-banner {temp_path}"
        
        result = os.system(cmd)
        if result != 0:
            raise CameraCaptureError("fswebcam命令执行失败")
        
        if not os.path.exists(temp_path):
            raise CameraCaptureError("fswebcam未生成图像文件")
        
        return temp_path
    
    def _capture_with_v4l2(self) -> Optional[str]:
        """使用v4l2采集图像"""
        # 检查v4l2设备
        v4l2_devices = glob.glob('/dev/video*')
        if not v4l2_devices:
            raise CameraCaptureError("未找到v4l2摄像头设备")
        
        device = v4l2_devices[0]  # 使用第一个设备
        timestamp = int(time.time())
        temp_path = os.path.join(self.temp_dir, f"v4l2_{timestamp}.jpg")
        
        # 使用ffmpeg截取图像
        cmd = f"ffmpeg -f v4l2 -i {device} -vframes 1 -y {temp_path} 2>/dev/null"
        
        result = os.system(cmd)
        if result != 0:
            raise CameraCaptureError("v4l2图像采集失败")
        
        if not os.path.exists(temp_path):
            raise CameraCaptureError("v4l2未生成图像文件")
        
        return temp_path
    
    def _get_moonraker_cameras(self) -> List[Dict]:
        """获取Moonraker摄像头配置"""
        try:
            # 这里需要从实际的Moonraker配置中获取摄像头信息
            # 暂时返回一个示例配置，实际实现时需要集成真实的配置获取逻辑
            cameras = []
            
            # 尝试从配置中获取摄像头信息
            camera_url = self.config.get_camera_url()
            if camera_url:
                cameras.append({
                    'name': 'default',
                    'stream_url': camera_url.rsplit('/', 1)[0] if '/' in camera_url else camera_url,
                    'snapshot_url': camera_url
                })
            
            return cameras
            
        except Exception as e:
            logging.error(f"获取Moonraker摄像头配置失败: {e}")
            return []
    
    def _build_snapshot_url(self, camera: Dict) -> str:
        """构建快照URL"""
        if 'snapshot_url' in camera:
            return camera['snapshot_url']
        elif 'stream_url' in camera:
            # 从流URL构建快照URL
            stream_url = camera['stream_url']
            if stream_url.endswith('/'):
                return f"{stream_url}snapshot"
            else:
                return f"{stream_url}/snapshot"
        else:
            raise CameraCaptureError("摄像头配置中缺少URL信息")
    
    def _save_image_data(self, image_data: bytes, source_type: str) -> str:
        """保存图像数据到临时文件"""
        timestamp = int(time.time())
        temp_path = os.path.join(self.temp_dir, f"{source_type}_{timestamp}.jpg")
        
        try:
            with open(temp_path, 'wb') as f:
                f.write(image_data)
            
            # 验证文件大小
            if os.path.getsize(temp_path) == 0:
                os.remove(temp_path)
                raise CameraCaptureError("保存的图像文件为空")
            
            # 清理旧文件
            self._cleanup_temp_files()
            
            return temp_path
            
        except Exception as e:
            # 清理失败的文件
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise CameraCaptureError(f"保存图像数据失败: {e}")
    
    def _cleanup_temp_files(self, max_files: int = 10):
        """清理临时文件"""
        try:
            # 获取所有快照文件
            pattern = os.path.join(self.temp_dir, "*_*.jpg")
            files = glob.glob(pattern)
            
            if len(files) > max_files:
                # 按创建时间排序，删除最旧的文件
                files.sort(key=os.path.getctime)
                files_to_delete = files[:-max_files]
                
                for file_path in files_to_delete:
                    try:
                        os.remove(file_path)
                        logging.debug(f"已删除旧的临时文件: {file_path}")
                    except Exception as e:
                        logging.warning(f"删除临时文件失败: {file_path}, {e}")
                        
        except Exception as e:
            logging.error(f"清理临时文件异常: {e}")
    
    def get_available_cameras(self) -> List[Dict]:
        """获取可用的摄像头列表"""
        cameras = []
        
        # Moonraker摄像头
        moonraker_cameras = self._get_moonraker_cameras()
        for cam in moonraker_cameras:
            cameras.append({
                'type': 'moonraker',
                'name': cam.get('name', 'Moonraker Camera'),
                'source': cam
            })
        
        # 本地摄像头设备
        v4l2_devices = glob.glob('/dev/video*')
        for i, device in enumerate(v4l2_devices):
            cameras.append({
                'type': 'local',
                'name': f'Local Camera {i}',
                'source': device
            })
        
        return cameras
    
    def test_camera_connection(self, source_type: str = None) -> bool:
        """测试摄像头连接"""
        try:
            source_type = source_type or self.config.get_camera_source()
            
            if source_type == "moonraker":
                cameras = self._get_moonraker_cameras()
                if not cameras:
                    return False
                
                # 测试第一个摄像头
                camera = cameras[0]
                snapshot_url = self._build_snapshot_url(camera)
                response = requests.get(snapshot_url, timeout=5)
                return response.status_code == 200
                
            elif source_type == "local":
                # 检查是否有可用的本地摄像头设备
                return len(glob.glob('/dev/video*')) > 0
                
            elif source_type == "url":
                camera_url = self.config.get_camera_url()
                if not camera_url:
                    return False
                response = requests.get(camera_url, timeout=5)
                return response.status_code == 200
                
            return False
            
        except Exception as e:
            logging.error(f"测试摄像头连接失败: {e}")
            return False