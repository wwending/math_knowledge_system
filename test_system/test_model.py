import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

# 设置绘图风格
plt.style.use('bmh')

def create_k_model_viz():
    # 初始化图形
    fig, ax = plt.subplots(figsize=(10, 8))
    plt.subplots_adjust(bottom=0.25)
    
    # 初始参数
    # 设直线底边总长为 10
    # D点位置 x_d (决定左边底边长 BD)
    # 左边高 h1 (AB)
    initial_bd = 4.0
    initial_ab = 3.0
    
    # 我们固定中间角为90度，且三角形ADE也是直角三角形
    # 根据相似三角形性质：AB/BD = CD/CE => h1/bd = (10-bd)/h2
    # 所以右边的高度 CE (h2) 是被动计算出来的
    
    # 绘制占位符
    line_ground, = ax.plot([], [], 'k-', lw=2)  # 底线 BC
    line_left, = ax.plot([], [], 'b-', lw=2, label='Triangle ABD')  # 左三角
    line_right, = ax.plot([], [], 'r-', lw=2, label='Triangle DCE') # 右三角
    line_mid, = ax.plot([], [], 'g--', lw=1.5, label='Right Angle ADE') # 中间直角
    
    # 标注点
    txt_similarity = ax.text(5, 8, '', ha='center', fontsize=12, color='purple')
    txt_ab = ax.text(0, 0, 'A', fontsize=10)
    txt_b = ax.text(0, 0, 'B', fontsize=10)
    txt_c = ax.text(0, 0, 'C', fontsize=10)
    txt_d = ax.text(0, 0, 'D', fontsize=10)
    txt_e = ax.text(0, 0, 'E', fontsize=10)

    ax.set_xlim(-1, 11)
    ax.set_ylim(-1, 10)
    ax.set_aspect('equal')
    ax.set_title('K-Shape Model: Similarity to Congruence\n("Line-Three-Right-Angles")', fontsize=14)
    ax.legend(loc='upper right')
    ax.grid(True)

    def update(val):
        bd = slider_bd.val
        ab = slider_ab.val
        
        # 计算各点坐标
        # B = (0, 0), C = (10, 0)
        # D = (bd, 0)
        # A = (0, ab)
        
        # 计算 E 点坐标
        # 利用相似性质：Triangle ABD ~ Triangle DCE
        # ratio k = CD / AB = CE / BD
        cd = 10.0 - bd
        
        # 几何推导：
        # angle B = angle C = 90
        # angle ADE = 90
        # => Triangle ABD ~ Triangle DCE
        # Ratio: AB/CD = BD/CE => CE = (BD * CD) / AB
        
        # 注意：这里我们反推E的位置以保证ADE是直角
        # 实际全等条件是：AB=CD 且 BD=CE
        # 为了演示，我们固定 A, B, C, D，计算 E 使得 ADE=90度
        # 根据相似：CE / CD = BD / AB => CE = (BD * CD) / AB
        
        if ab == 0: ce = 0 # 防止除零
        else: ce = (bd * cd) / ab
        
        # 坐标定义
        xB, yB = 0, 0
        xC, yC = 10, 0
        xD, yD = bd, 0
        xA, yA = 0, ab
        xE, yE = 10, ce
        
        # 更新线条数据
        # 左三角形 A-B-D-A
        line_left.set_data([xA, xB, xD, xA], [yA, yB, yD, yA])
        # 右三角形 D-C-E-D
        line_right.set_data([xD, xC, xE, xD], [yD, yC, yE, yD])
        # 连接 A-E 形成直角顶 (辅助看图)
        line_mid.set_data([xA, xD, xE], [yA, yD, yE])
        # 底线
        line_ground.set_data([xB, xC], [yB, yC])
        
        # 更新文字位置
        txt_ab.set_position((xA-0.5, yA))
        txt_b.set_position((xB-0.5, yB))
        txt_c.set_position((xC+0.2, yC))
        txt_d.set_position((xD, -0.8))
        txt_e.set_position((xE+0.2, yE))
        
        # 判断全等
        # 全等条件：AB = CD (即 ab = 10-bd)
        is_congruent = np.isclose(ab, cd, atol=0.1)
        
        if is_congruent:
            txt_similarity.set_text(f"STATUS: CONGRUENT (全等)!\nAB ({ab:.1f}) ≈ CD ({cd:.1f})")
            txt_similarity.set_color('green')
            txt_similarity.set_fontweight('bold')
        else:
            txt_similarity.set_text(f"STATUS: SIMILAR (相似)\nRatio AB/CD = {ab/cd:.2f}")
            txt_similarity.set_color('blue')
            txt_similarity.set_fontweight('normal')
            
        fig.canvas.draw_idle()

    # 创建滑块
    # 滑块1：D点的位置 (改变底边 BD 的长度)
    ax_bd = plt.axes([0.25, 0.1, 0.65, 0.03])
    slider_bd = Slider(ax_bd, 'Position D (BD)', 1.0, 9.0, valinit=initial_bd)
    
    # 滑块2：A点的高度 (改变 AB 的长度)
    ax_ab = plt.axes([0.25, 0.05, 0.65, 0.03])
    slider_ab = Slider(ax_ab, 'Height AB', 1.0, 8.0, valinit=initial_ab)

    slider_bd.on_changed(update)
    slider_ab.on_changed(update)

    update(None) # 初始绘制
    plt.show()

if __name__ == "__main__":
    create_k_model_viz()