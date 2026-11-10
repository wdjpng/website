import cv2, numpy as np, os
names=['up','down','left_up','right_down','up_close','down_close']
rows=[]
for n in names:
    a=cv2.imread(f'/tmp/pano_test/before/{n}.png'); b=cv2.imread(f'/tmp/pano_test/after/{n}.png')
    if a is None or b is None: continue
    a=cv2.resize(a,(480,360)); b=cv2.resize(b,(480,360))
    cv2.putText(a,n+' before',(8,24),0,0.7,(0,255,255),2); cv2.putText(b,n+' after',(8,24),0,0.7,(0,255,255),2)
    rows.append(np.hstack([a,b]))
cv2.imwrite(os.path.expanduser('~/room/work_pano/sbs.jpg'), np.vstack(rows))
print(len(rows))
