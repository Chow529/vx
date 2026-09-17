"""生成 tabbar 占位图标"""
from PIL import Image, ImageDraw
import os

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mini', 'images')
os.makedirs(out_dir, exist_ok=True)

icon_names = ['community', 'question', 'post', 'profile']
size = 81

for name in icon_names:
    # 普通 (灰色)
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([15, 15, 66, 66], fill=(153, 153, 153, 255))
    img.save(os.path.join(out_dir, f'{name}.png'))

    # 选中 (蓝色)
    img2 = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw2 = ImageDraw.Draw(img2)
    draw2.ellipse([15, 15, 66, 66], fill=(74, 144, 217, 255))
    img2.save(os.path.join(out_dir, f'{name}-active.png'))

# 默认头像
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([5, 5, 76, 76], fill=(200, 200, 200, 255))
draw.ellipse([25, 20, 56, 48], fill=(150, 150, 150, 255))  # 头
draw.arc([15, 45, 66, 80], 0, 180, fill=(150, 150, 150, 255), width=3)  # 身体
img.save(os.path.join(out_dir, 'default-avatar.png'))

print(f'图标已生成到 {out_dir}')
