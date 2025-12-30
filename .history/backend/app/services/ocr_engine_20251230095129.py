import time
from pix2text import Pix2Text
from loguru import logger

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

    def initialize(self):
        """
        显式初始化模型。建议在应用启动时调用。
        """
        if self._model is not None:
            logger.info("OCR 模型已经加载，跳过初始化。")
            return

        logger.info("正在加载 Pix2Text 理科 OCR 模型 (这可能需要几分钟下载权重)...")
        start_time = time.time()
        
        try:
            # 初始化 Pix2Text
            # device='cuda' 强制使用你的 RTX 2060
            self._model = Pix2Text.from_config(device='cuda')
            
            cost = time.time() - start_time
            logger.success(f"OCR 模型加载完成！耗时: {cost:.2f}s | 设备: CUDA (RTX 2060)")
        except Exception as e:
            logger.error(f"OCR 模型加载失败: {e}")
            raise e

    def recognize(self, image_path: str) -> dict:
        """
        核心识别方法
        :param image_path: 图片的本地路径
        :return: 包含 markdown 文本和耗时的字典
        """
        if self._model is None:
            # 防止忘记初始化
            self.initialize()

        logger.info(f"开始识别图片: {image_path}")
        start_time = time.time()

        try:
            # 核心调用: recognize_text
            # resized_shape=600 是一个平衡点，图片太大显存会爆，太小识别不清
            result = self._model.recognize_text(
                image_path,
                resized_shape=600,
                file_type='text_formula', # 混合模式：文字+公式
                save_analysis_res=None    # 不保存中间结果图片
            )
            
            # Pix2Text 的返回值通常是一个字符串（Markdown格式）
            # 注意：不同版本返回值结构可能略有不同，这里假设返回的是字符串
            # 如果是列表，我们将其拼接
            if isinstance(result, list):
                markdown_content = "\n".join([item.get('text', '') for item in result])
            elif isinstance(result, dict):
                 markdown_content = result.get('text', '')
            else:
                markdown_content = str(result)

            cost = time.time() - start_time
            logger.info(f"识别结束，耗时: {cost:.2f}s")

            return {
                "success": True,
                "content": markdown_content,
                "cost_seconds": round(cost, 3)
            }

        except Exception as e:
            logger.error(f"识别过程中发生错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": ""
            }

# 创建一个全局实例供外部调用
ocr_service = OCREngine()