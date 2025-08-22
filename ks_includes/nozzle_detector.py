"""
Nozzle Detection Module
用于自动检测和校准双喷嘴XY偏移
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional, List
import time


class NozzleDetector:
    """喷嘴检测器，用于自动校准双喷嘴偏移"""
    
    def __init__(self, pixel_to_mm_ratio: float = 0.05):
        """
        初始化喷嘴检测器
        
        Args:
            pixel_to_mm_ratio: 像素到毫米的转换比例（默认0.05mm/pixel）
        """
        self.pixel_to_mm = pixel_to_mm_ratio
        self.debug_mode = True
        
    def capture_nozzle_image(self, camera_url: str, save_path: str = None) -> np.ndarray:
        """
        从摄像头捕获喷嘴图像
        
        Args:
            camera_url: 摄像头URL
            save_path: 可选的保存路径
            
        Returns:
            捕获的图像数组
        """
        import requests
        from PIL import Image
        from io import BytesIO
        
        try:
            # 从URL获取图像
            response = requests.get(camera_url, timeout=5)
            img = Image.open(BytesIO(response.content))
            
            # 转换为OpenCV格式
            image = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            if save_path:
                cv2.imwrite(save_path, image)
                
            return image
            
        except Exception as e:
            logging.error(f"捕获图像失败: {e}")
            return None
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        预处理图像以增强喷嘴轮廓
        
        Args:
            image: 原始图像
            
        Returns:
            预处理后的二值图像
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 应用高斯模糊减少噪声
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 使用CLAHE增强对比度
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        # 边缘检测
        edges = cv2.Canny(enhanced, 50, 150)
        
        # 形态学操作 - 闭运算连接边缘
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        return closed
    
    def detect_nozzle_contours(self, preprocessed_image: np.ndarray) -> List[np.ndarray]:
        """
        检测喷嘴轮廓
        
        Args:
            preprocessed_image: 预处理后的图像
            
        Returns:
            检测到的喷嘴轮廓列表
        """
        # 查找轮廓
        contours, _ = cv2.findContours(preprocessed_image, 
                                       cv2.RETR_EXTERNAL, 
                                       cv2.CHAIN_APPROX_SIMPLE)
        
        # 过滤轮廓 - 根据面积和形状
        nozzle_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # 喷嘴通常有一定的面积范围
            if 500 < area < 5000:  # 需要根据实际情况调整
                # 计算轮廓的圆形度
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    
                    # 喷嘴轮廓通常接近圆形
                    if circularity > 0.5:  # 阈值可调整
                        nozzle_contours.append(contour)
        
        # 按面积排序，取最大的两个轮廓（两个喷嘴）
        nozzle_contours.sort(key=cv2.contourArea, reverse=True)
        return nozzle_contours[:2]
    
    def find_nozzle_centers(self, contours: List[np.ndarray]) -> List[Tuple[float, float]]:
        """
        找到喷嘴中心点
        
        Args:
            contours: 喷嘴轮廓列表
            
        Returns:
            喷嘴中心点坐标列表
        """
        centers = []
        
        for contour in contours:
            # 方法1：使用矩计算质心
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                
                # 亚像素精度优化
                # 将轮廓点转换为合适的格式
                contour_points = contour.reshape(-1, 2).astype(np.float32)
                
                # 使用最小外接圆获得更精确的中心
                (x, y), radius = cv2.minEnclosingCircle(contour_points)
                
                # 使用加权平均获得最终中心
                final_cx = (cx + x) / 2
                final_cy = (cy + y) / 2
                
                centers.append((final_cx, final_cy))
        
        return centers
    
    def calculate_offset(self, centers: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """
        计算两个喷嘴之间的偏移
        
        Args:
            centers: 喷嘴中心点列表
            
        Returns:
            XY偏移量（毫米）
        """
        if len(centers) < 2:
            logging.error("未检测到足够的喷嘴")
            return None
        
        # 计算像素偏移
        pixel_offset_x = centers[1][0] - centers[0][0]
        pixel_offset_y = centers[1][1] - centers[0][1]
        
        # 转换为毫米
        mm_offset_x = pixel_offset_x * self.pixel_to_mm
        mm_offset_y = pixel_offset_y * self.pixel_to_mm
        
        return (mm_offset_x, mm_offset_y)
    
    def detect_nozzles_with_template(self, image: np.ndarray, template_path: str = None) -> List[Tuple[float, float]]:
        """
        使用模板匹配检测喷嘴（备选方案）
        
        Args:
            image: 输入图像
            template_path: 喷嘴模板图像路径
            
        Returns:
            检测到的喷嘴位置列表
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 如果没有提供模板，使用圆形Hough变换检测
        if template_path is None:
            # 使用霍夫圆检测
            circles = cv2.HoughCircles(gray, 
                                      cv2.HOUGH_GRADIENT,
                                      dp=1,
                                      minDist=50,
                                      param1=50,
                                      param2=30,
                                      minRadius=10,
                                      maxRadius=50)
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                centers = [(float(x), float(y)) for x, y, r in circles[0, :2]]
                return centers
        else:
            # 使用模板匹配
            template = cv2.imread(template_path, 0)
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            
            # 找到匹配位置
            threshold = 0.8
            locations = np.where(result >= threshold)
            
            centers = []
            for pt in zip(*locations[::-1]):
                # 计算模板中心
                h, w = template.shape
                center = (pt[0] + w/2, pt[1] + h/2)
                centers.append(center)
            
            return centers[:2]  # 返回前两个匹配
        
        return []
    
    def auto_calibrate(self, image_or_path, use_template: bool = False) -> Optional[Tuple[float, float]]:
        """
        自动校准主函数
        
        Args:
            image_or_path: 图像数组或图像路径
            use_template: 是否使用模板匹配
            
        Returns:
            XY偏移量（毫米）或None
        """
        # 加载图像
        if isinstance(image_or_path, str):
            image = cv2.imread(image_or_path)
        else:
            image = image_or_path
        
        if image is None:
            logging.error("无法加载图像")
            return None
        
        if use_template:
            # 使用模板匹配方法
            centers = self.detect_nozzles_with_template(image)
        else:
            # 使用轮廓检测方法
            preprocessed = self.preprocess_image(image)
            contours = self.detect_nozzle_contours(preprocessed)
            centers = self.find_nozzle_centers(contours)
        
        if len(centers) >= 2:
            offset = self.calculate_offset(centers)
            
            if self.debug_mode and offset:
                # 绘制检测结果
                debug_image = image.copy()
                for i, (cx, cy) in enumerate(centers):
                    # 绘制中心点
                    cv2.circle(debug_image, (int(cx), int(cy)), 5, (0, 255, 0), -1)
                    # 绘制标签
                    cv2.putText(debug_image, f"Nozzle {i+1}", 
                              (int(cx-30), int(cy-20)),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # 绘制偏移线
                if len(centers) >= 2:
                    cv2.line(debug_image, 
                           (int(centers[0][0]), int(centers[0][1])),
                           (int(centers[1][0]), int(centers[1][1])),
                           (0, 0, 255), 2)
                    
                    # 显示偏移值
                    mid_x = int((centers[0][0] + centers[1][0]) / 2)
                    mid_y = int((centers[0][1] + centers[1][1]) / 2)
                    cv2.putText(debug_image, 
                              f"Offset: ({offset[0]:.2f}, {offset[1]:.2f}) mm",
                              (mid_x - 60, mid_y - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # 保存调试图像
                cv2.imwrite("/tmp/nozzle_detection_debug.png", debug_image)
                logging.info("调试图像已保存到 /tmp/nozzle_detection_debug.png")
            
            return offset
        
        return None
    
    def calibrate_pixel_ratio(self, known_distance_mm: float, 
                            measured_pixels: float) -> float:
        """
        校准像素到毫米的转换比例
        
        Args:
            known_distance_mm: 已知的实际距离（毫米）
            measured_pixels: 测量的像素距离
            
        Returns:
            新的像素到毫米转换比例
        """
        if measured_pixels > 0:
            self.pixel_to_mm = known_distance_mm / measured_pixels
            logging.info(f"像素比例已校准: {self.pixel_to_mm:.4f} mm/pixel")
            return self.pixel_to_mm
        return self.pixel_to_mm