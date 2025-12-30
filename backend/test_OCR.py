import os
import sys

# 将当前目录加入 python 路径，确保能找到 app 模块
sys.path.append(os.getcwd())

from app.services.ocr_engine import ocr_service

def run_test():
    # 1. 图片路径 (请确保这里有张图！)
    img_path = os.path.join("..", "test_data", "images", "test_math.jpg")
    
    # 检查图片是否存在
    if not os.path.exists(img_path):
        print(f"❌ 错误：找不到测试图片 {img_path}")
        print("请先找一张数学题截图，放在 test_data/images/ 目录下，并命名为 test_math.jpg")
        return

    print("🚀 正在启动 OCR 服务测试...")
    
    # 2. 第一次运行会自动下载模型 (约 300MB - 1GB)，请耐心等待
    # 也会触发显存加载
    ocr_service.initialize()
    
    # 3. 执行识别
    print("\n📸 正在读取图片并推理...")
    result = ocr_service.recognize(img_path)
    
    if result["success"]:
        print("\n" + "="*20 + " 识别结果 (Markdown) " + "="*20)
        print(result["content"])
        print("="*60)
        print(f"⏱️ 耗时: {result['cost_seconds']} 秒")
    else:
        print(f"❌ 识别失败: {result['error']}")

if __name__ == "__main__":
    run_test()