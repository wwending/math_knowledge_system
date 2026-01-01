import time
from pix2text import Pix2Text
from loguru import logger

import os
from pix2text import Pix2Text
from loguru import logger
from PIL import Image, ImageEnhance # <--- 引入 PIL

class OCREngine:
    _instance = None
    _model = None

    def __new__(cls):
        """
        实现单例模式：确保整个应用生命周期内只有一个 OCREngine 实例
        """
        if cls._instance is None:
            cls._instance = super(OCREngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.p2t = None

    def initialize(self):
        logger.info("正在加载本地 OCR 模型 (Pix2Text)，这可能需要一点时间...")
        try:
            # ⚡️ 关键优化 1: 调整模型参数
            # analyzer_config: 负责版面分析的参数
            # formula_config: 负责公式识别的参数
            # 调大 resized_shape 可以让模型看清更小的字 (默认是 768左右)
            self.p2t = Pix2Text.from_config(
                total_config={
                    "layout": {"scores_thresh": 0.5}, # 稍微降低版面分析的阈值
                    "formula": {"resized_shape": 1024}, # ⚡️ 放大输入给公式模型的尺寸
                    "text": {"resized_shape": 1024}     # ⚡️ 放大输入给文本模型的尺寸
                }
            )
            logger.success("OCR 模型加载完毕！")
        except Exception as e:
            logger.critical(f"OCR 模型加载严重失败: {e}")
            raise e

    # --- 🆕 新增：图像增强预处理函数 ---
    def preprocess_image(self, image_path: str) -> Image.Image:
        """
        对图片进行预处理：放大、锐化、增加对比度，帮助 OCR 识别小字符和模糊字符。
        """
        try:
            img = Image.open(image_path)
            
            # 1. 转换为 RGB (防止 PNG 透明图层问题)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # 2. 放大图片 (Upscale)
            # 如果图片宽度小于 1000px，强行放大到 1500px 宽，高按比例缩放
            # 这对于识别上标、下标非常关键
            target_width = 1500
            if img.width < target_width:
                ratio = target_width / img.width
                new_height = int(img.height * ratio)
                # 使用高质量的重采样滤镜
                img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"图片已自动放大到: {img.size}")

            # 3. 增强对比度 (解决 A 变 4, 3 变 5 的问题)
            contrast = ImageEnhance.Contrast(img)
            img = contrast.enhance(1.5) # 提高 50% 对比度

            # 4. 锐化 (让边缘更清晰)
            sharpness = ImageEnhance.Sharpness(img)
            img = sharpness.enhance(2.0) # 提高 100% 锐度

            # (可选) 保存预处理后的图片看看效果，调试完可以注释掉
            # debug_path = image_path.replace(".", "_debug.")
            # img.save(debug_path)
            # logger.debug(f"已保存预处理增强图片: {debug_path}")
            
            return img

        except Exception as e:
            logger.warning(f"图片预处理失败，将使用原图: {e}")
            return Image.open(image_path) # 保底方案

    

    def recognize(self, image_path: str):
        if not self.p2t:
            raise RuntimeError("OCR 服务未初始化")
        
        if not os.path.exists(image_path):
            return {"success": False, "error": "文件不存在", "content": ""}

        try:
            logger.info(f"开始识别图片: {image_path}")
            
            # ⚡️ 关键优化 2: 使用预处理后的图片对象，而不是路径
            processed_img = self.preprocess_image(image_path)

            # 调用 Pix2Text 识别
            # resized_shape在这也可以传，但我们在初始化时配置更好
            result = self.p2t.recognize(processed_img)

            final_content = result
            logger.info(f"识别完成 (长度: {len(final_content)})")
            logger.debug(f"原始 OCR 结果:\n{final_content}")

            return {
                "success": True,
                "content": final_content,
                "raw_result": result, 
                "cost_seconds": 0.0 
            }

        except Exception as e:
            logger.error(f"识别过程出错: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": ""
            }

# 创建一个全局实例供外部调用
ocr_service = OCREngine()