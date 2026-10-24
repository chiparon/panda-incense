"""Pack source animation frames into the installed Codex v2 grid."""
from pathlib import Path
from collections import deque
import json, shutil
from PIL import Image, ImageSequence, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CELL = (192, 208)

def fit(im, height=174):
    box = im.getbbox()
    if not box: raise ValueError('Empty frame')
    im = im.crop(box)
    scale = min(168/im.width, height/im.height)
    im = im.resize((round(im.width*scale), round(im.height*scale)), Image.Resampling.LANCZOS)
    out = Image.new('RGBA', CELL)
    out.alpha_composite(im, ((192-im.width)//2, 194-im.height))
    return out

def original_frames():
    frames=[]
    for raw in ImageSequence.Iterator(Image.open(ROOT/'pandaincence.gif')):
        im=raw.convert('RGBA'); p=im.load(); w,h=im.size
        # GIF uses an opaque exterior white matte. Color-key only border-connected
        # background during import; preserve white head, body, eye lines and timing.
        q=deque([(x,0) for x in range(w)]+[(x,h-1) for x in range(w)]+
                [(0,y) for y in range(h)]+[(w-1,y) for y in range(h)])
        seen=set()
        while q:
            x,y=q.popleft()
            if (x,y) in seen or not(0<=x<w and 0<=y<h): continue
            seen.add((x,y)); r,g,b,a=p[x,y]
            if min(r,g,b)<235: continue
            p[x,y]=(r,g,b,0)
            q.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
        frames.append(fit(im))
    return frames

def cells(path, columns, rows, uniform=False):
    src=Image.open(path).convert('RGBA');result=[]
    for r in range(rows):
        for c in range(columns):
            box=(round(c*src.width/columns),round(r*src.height/rows),
                 round((c+1)*src.width/columns),round((r+1)*src.height/rows))
            tile=src.crop(box)
            # Generated rows are not perfectly aligned: discard disconnected
            # fragments belonging to the neighboring sprite at cell boundaries.
            alpha=tile.getchannel('A');w,h=tile.size
            opaque=set((x,y) for y in range(h) for x in range(w) if alpha.getpixel((x,y))>=32)
            largest=set()
            while opaque:
                first=opaque.pop();component={first};q=[first]
                while q:
                    x,y=q.pop()
                    for pt in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                        if pt in opaque:opaque.remove(pt);component.add(pt);q.append(pt)
                if len(component)>len(largest):largest=component
            mask=Image.new('L',tile.size)
            for pt in largest:mask.putpixel(pt,255)
            mask=mask.filter(ImageFilter.MaxFilter(3))
            from PIL import ImageChops
            tile.putalpha(ImageChops.multiply(alpha,mask))
            result.append(tile if uniform else fit(tile))
    if uniform:
        scale=min(176/max(t.width for t in result),174/max(t.getbbox()[3]-t.getbbox()[1] for t in result))
        packed=[]
        for tile in result:
            bottom=tile.getbbox()[3]
            resized=tile.resize((round(tile.width*scale),round(tile.height*scale)),Image.Resampling.LANCZOS)
            frame=Image.new('RGBA',CELL)
            frame.alpha_composite(resized,((192-resized.width)//2,194-round(bottom*scale)))
            packed.append(frame)
        return packed
    return result

def main():
    src=cells(ROOT/'assets/actions-source.png',8,8)
    gaze=cells(ROOT/'assets/gaze-source.png',4,4)
    actions={'incense':original_frames()}
    names=['roll-right','roll-left','laugh','jump','recover','bamboo','laptop','review']
    for i,name in enumerate(names):actions[name]=src[i*8:i*8+8]
    actions['laugh']=cells(ROOT/'assets/laugh-source-v3.png',4,2,uniform=True)
    actions['gaze']=gaze
    rows=[('idle','incense',[0,1,3,5,6,7]),
          ('running-right','roll-right',list(range(8))),
          ('running-left','roll-left',list(range(8))),
          ('waving','laugh',[0,1,2,4]),
          ('jumping','jump',[0,1,2,4,6]),
          ('failed','recover',list(range(8))),
          ('waiting','bamboo',[0,1,2,3,4,6]),
          ('running','laptop',[0,1,2,3,4,6]),
          ('review','review',[0,1,2,3,4,7]),
          ('gaze-1','gaze',list(range(8))),
          ('gaze-2','gaze',list(range(8,16)))]
    sheet=Image.new('RGBA',(1536,2288)); mapping=[]
    for r,(state,name,indices) in enumerate(rows):
        for c in range(8):
            frame=actions[name][indices[min(c,len(indices)-1)]]
            sheet.alpha_composite(frame,(c*192,r*208))
        mapping.append(dict(row=r,state=state,action=name,frames=len(indices)))
    sheet.save(ROOT/'panda-incense/spritesheet.png')
    (ROOT/'panda-incense/pet.json').write_text(json.dumps(dict(
        displayName='熊猫烧香',description='点头烧香、打滚、捧腹大笑、敲电脑、抱竹等待和检查清单。',
        spriteVersionNumber=2,spritesheetPath='spritesheet.png'),ensure_ascii=False,indent=2),encoding='utf8')
    for name,frames in actions.items():
        folder=ROOT/'actions'/name;folder.mkdir(parents=True,exist_ok=True)
        for n,frame in enumerate(frames):frame.save(folder/f'{n:02}.png')
    (ROOT/'actions/manifest.json').write_text(json.dumps({k:len(v) for k,v in actions.items()},indent=2))
    (ROOT/'state-map.json').write_text(json.dumps({'nativeRows':mapping,'companionEvents':{
        'task_started':'laptop','task_complete':'review','turn_aborted':'recover',
        'request_user_input':'bamboo','click':'laugh','drag':'roll-right / roll-left',
        'idle':'incense','idle_break':'bamboo / jump / roll-right'}},ensure_ascii=False,indent=2),encoding='utf8')
    contact=Image.new('RGB',(960,640),'#e9e5dc');draw=ImageDraw.Draw(contact)
    for i,(name,frames) in enumerate(actions.items()):
        x=(i%5)*192;y=(i//5)*320
        frame=frames[2 if name!='incense' else 0]
        contact.paste(frame,(x,y+36),frame)
        draw.text((x+20,y+258),name,fill='#363a39')
    contact.save(ROOT/'assets/contact.png')
    shutil.make_archive(str(ROOT/'panda-incense-native'),'zip',ROOT,'panda-incense')
    print('Built native atlas, 88 cells, full action library and ZIP.')

if __name__=='__main__':main()
