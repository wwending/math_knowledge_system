import fitz  # PyMuPDF
import os

# --- 配置区域 ---
# 1. 把你的PDF文件路径填在这里 (注意要把单斜杠 \ 改成双斜杠 \\ 或者反斜杠 /)
pdf_path = r"D:\基础版2026电子版\第8章 数列\模块1 等差、等比数列问题\第1节 等差、等比数列的基本公式 （方法册+习题册）.pdf" 

# 2. 你想提取哪一页？(0 代表第1页，5 代表第6页)
page_num = 5  

# 3. 放大倍数 (关键参数！3 表示 300% 放大，通常足够高清)
zoom_x = 3.0 
zoom_y = 3.0
# ----------------

def convert_to_hd_image():
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        print(f"❌ 错误：找不到文件 -> {pdf_path}")
        return

    try:
        # 打开 PDF
        doc = fitz.open(pdf_path)
        print(f"✅ 成功打开 PDF，总页数：{doc.page_count}")

        # 加载指定页面
        page = doc.load_page(page_num)

        # 设置变换矩阵 (Matrix)，这就是高清的秘密
        # 默认 72 DPI，放大 3 倍后约 216 DPI，放大 4 倍约 288 DPI
        mat = fitz.Matrix(zoom_x, zoom_y)

        # 渲染页面为图像 (Pixmap)
        print("⏳ 正在渲染高清图像...")
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # 保存结果
        output_filename = f"hd_output_page_{page_num}.png"
        pix.save(output_filename)
        
        print(f"🎉 成功！图片已保存为: {output_filename}")
        print(f"📏 图片尺寸: {pix.width} x {pix.height} (超级清晰)")
        print("👉 快去文件夹里打开看看效果吧！")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    convert_to_hd_image()