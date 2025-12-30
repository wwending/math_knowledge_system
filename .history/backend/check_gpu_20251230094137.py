import torch
import time

def check_setup():
    print("-" * 30)
    print("正在检查环境配置...")
    
    # 1. 检查 CUDA 是否可用
    if torch.cuda.is_available():
        print("✅ CUDA 可用! (恭喜，PyTorch 能看到你的显卡)")
        
        # 2. 获取显卡信息
        gpu_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🎮 显卡型号: {gpu_name}")
        print(f"💾 显存大小: {total_memory:.2f} GB")
        
        # 3. 做一个简单的矩阵运算测试速度
        print("\n正在进行简单的 GPU 计算测试...")
        x = torch.rand(5000, 5000).cuda()
        y = torch.rand(5000, 5000).cuda()
        
        start = time.time()
        z = torch.matmul(x, y) # 矩阵乘法
        end = time.time()
        
        print(f"⚡ 5000x5000 矩阵乘法耗时: {end - start:.4f} 秒")
        print("环境完美，可以开始做 OCR 了！")
    else:
        print("❌ CUDA 不可用。PyTorch 目前正在使用 CPU。")
        print("请检查：1. 是否安装了 CUDA 版 PyTorch？ 2. 显卡驱动是否正常？")
    
    print("-" * 30)

if __name__ == "__main__":
    check_setup()