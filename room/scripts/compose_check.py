import sys, os
from PIL import Image, ImageDraw, ImageFont
gt_dir, before_dir, after_dir, out = sys.argv[1:5]
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
rows = []
for i in range(6):
    n = f'chk_{i}'
    paths = [f'{gt_dir}/{n}.png', f'{before_dir}/{n}.png', f'{after_dir}/{n}.png']
    ims = [Image.open(p).convert('RGB').resize((600, 450), Image.LANCZOS) if os.path.exists(p) else Image.new('RGB', (600, 450)) for p in paths]
    r = Image.new('RGB', (600 * 3 + 24, 450 + 34), (24, 24, 24))
    for j, (im, lab) in enumerate(zip(ims, ['Blender Cycles', 'before', 'after'])):
        r.paste(im, (j * 612, 34)); ImageDraw.Draw(r).text((j * 612 + 6, 5), lab, fill=(230, 230, 230), font=font)
    rows.append(r)
sheet = Image.new('RGB', (rows[0].width, sum(r.height + 10 for r in rows)), (24, 24, 24))
y = 0
for r in rows: sheet.paste(r, (0, y)); y += r.height + 10
sheet.save(out, quality=88)
print(out, sheet.size)
