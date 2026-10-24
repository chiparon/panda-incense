"""Local Windows deskpet. Reads Codex events; never writes Codex state."""
from pathlib import Path
import argparse, json, os, random, sqlite3, time
from contextlib import closing

ROOT=Path(__file__).resolve().parent
CODEX=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))

class EventTail:
    def __init__(self,path):
        self.path=Path(path);self.offset=0;self.state='idle';self.timestamp=''
    def feed(self,d):
        p=d.get('payload',{});kind=p.get('type');typ=d.get('type')
        if typ=='event_msg':
            if kind=='task_started':self.state='laptop'
            elif kind=='task_complete':self.state='review'
            elif kind in ('turn_aborted','task_failed'):self.state='recover'
            elif kind in ('user_input_requested','approval_requested'):self.state='bamboo'
            elif kind in ('user_input_response','approval_response'):self.state='laptop'
            else:return
            self.timestamp=d.get('timestamp','')
        elif typ=='response_item':
            if kind=='function_call' and 'request_user_input' in p.get('name',''):
                self.state='bamboo';self.timestamp=d.get('timestamp','')
            elif kind=='function_call_output' and self.state=='bamboo':self.state='laptop'
    def poll(self):
        if not self.path.exists():return
        if self.path.stat().st_size<self.offset:self.offset=0;self.state='idle'
        with self.path.open('rb') as f:
            f.seek(self.offset)
            while True:
                start=f.tell();line=f.readline()
                if not line or not line.endswith(b'\n'):self.offset=start;break
                try:self.feed(json.loads(line))
                except (ValueError,TypeError):pass

class Watcher:
    def __init__(self,workspace=ROOT,codex=CODEX):
        self.workspace=str(workspace);self.codex=Path(codex);self.tails={};self.error=None
    def poll(self):
        db=self.codex/'state_5.sqlite'
        if not db.exists():self.error='未找到 Codex 本地会话库';return 'idle'
        try:
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=.3)) as c:
                c.create_function('normpath',1,lambda s:s.replace('\\','/').removeprefix('//?/').rstrip('/').lower())
                rows=c.execute('SELECT id,rollout_path FROM threads WHERE archived=0 AND normpath(cwd)=normpath(?) ORDER BY updated_at DESC',(self.workspace,)).fetchall()
            live={}
            for tid,path in rows:
                tail=self.tails.get(tid) or EventTail(path);tail.poll();live[tid]=tail
            self.tails=live;self.error=None
            states=[x.state for x in live.values()]
            if 'laptop' in states:return 'laptop'
            if 'bamboo' in states:return 'bamboo'
            latest=max(live.values(),key=lambda x:x.timestamp,default=None)
            return latest.state if latest else 'idle'
        except (sqlite3.Error,OSError) as e:
            self.error=str(e);return 'idle'

class Pet:
    def __init__(self,args):
        import tkinter as tk
        from PIL import Image, ImageTk
        self.tk=tk;self.root=tk.Tk();self.root.title('熊猫烧香 · Codex deskpet')
        self.root.overrideredirect(True);self.root.attributes('-topmost',True)
        self.root.configure(bg='#ff00ff');self.root.wm_attributes('-transparentcolor','#ff00ff')
        self.size=args.size;self.height=round(args.size*208/192)
        self.root.geometry(f'{self.size}x{self.height}+{self.root.winfo_screenwidth()-self.size-45}+{self.root.winfo_screenheight()-self.height-85}')
        self.canvas=tk.Canvas(self.root,width=self.size,height=self.height,highlightthickness=0,bg='#ff00ff');self.canvas.pack()
        manifest=json.loads((ROOT/'actions/manifest.json').read_text())
        self.frames={}
        for name,count in manifest.items():
            self.frames[name]=[]
            for n in range(count):
                im=Image.open(ROOT/'actions'/name/f'{n:02}.png').convert('RGBA').resize((self.size,self.height),Image.Resampling.LANCZOS)
                # Windows Tk color key needs binary alpha; native PNG keeps full alpha.
                im.putalpha(im.getchannel('A').point(lambda a:255 if a>=128 else 0))
                self.frames[name].append(ImageTk.PhotoImage(im))
        self.item=self.canvas.create_image(0,0,anchor='nw');self.action='incense';self.frame=0
        self.base='idle';self.override_until=0;self.next_break=time.monotonic()+25
        self.drag=None;self.watcher=Watcher(args.workspace);self.auto=True;self.status='idle'
        self.menu=tk.Menu(self.root,tearoff=0)
        for label,name in [('点头烧香（原 GIF）','incense'),('打滚 →','roll-right'),('打滚 ←','roll-left'),('捧腹大笑','laugh'),('拿出电脑打字','laptop'),('开心跳跃','jump'),('擦汗振作','recover'),('抱竹等待','bamboo'),('检查清单','review')]:
            self.menu.add_command(label=label,command=lambda n=name:self.play(n,4))
        self.menu.add_separator();self.menu.add_command(label='恢复工作联动',command=self.resume)
        self.menu.add_command(label='暂停工作联动',command=self.pause)
        self.menu.add_command(label='退出',command=self.root.destroy)
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.move)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',lambda e:self.menu.tk_popup(e.x_root,e.y_root))
        self.root.bind('<Escape>',lambda e:self.root.destroy())
        self.root.after(50,self.tick);self.root.after(100,self.poll)
        if args.test_seconds:self.root.after(int(args.test_seconds*1000),self.root.destroy)
        self.root.mainloop()
    def resume(self):self.auto=True;self.override_until=0
    def pause(self):self.auto=False;self.play('incense',0)
    def set_action(self,name):
        if self.action!=name:self.action=name;self.frame=0
    def play(self,name,seconds=2.5):
        self.action=name;self.frame=0;self.override_until=time.monotonic()+seconds
    def press(self,e):self.drag=(e.x_root,e.y_root,self.root.winfo_x(),self.root.winfo_y(),False)
    def move(self,e):
        if not self.drag:return
        x,y,wx,wy,moved=self.drag;dx=e.x_root-x;dy=e.y_root-y
        if abs(dx)+abs(dy)>5:
            self.drag=(x,y,wx,wy,True);self.root.geometry(f'+{max(0,wx+dx)}+{max(0,wy+dy)}')
            self.set_action('roll-right' if dx>=0 else 'roll-left');self.override_until=time.monotonic()+.5
    def release(self,e):
        if self.drag and not self.drag[4]:self.play('laugh',2.6)
        self.drag=None
    def poll(self):
        state=self.watcher.poll();now=time.monotonic()
        if state!=self.base:
            self.base=state
            if self.auto and now>=self.override_until:
                if state in ('review','recover'):self.play(state,3)
                else:self.set_action('incense' if state=='idle' else state)
        (ROOT/'runtime-status.json').write_text(json.dumps(dict(pid=os.getpid(),state=state,action=self.action,workspace=self.watcher.workspace,error=self.watcher.error,updated=time.time()),ensure_ascii=False),encoding='utf8')
        self.root.after(2000,self.poll)
    def tick(self):
        now=time.monotonic()
        if self.auto and now>=self.override_until and not self.drag:
            target=self.base if self.base in ('laptop','bamboo') else 'incense'
            self.set_action(target)
            if target=='incense' and now>=self.next_break:
                self.play(random.choice(['bamboo','jump','roll-right']),2.4);self.next_break=now+random.uniform(24,40)
        frames=self.frames[self.action];self.canvas.itemconfigure(self.item,image=frames[self.frame])
        self.frame+=1
        if self.frame>=len(frames):self.frame=2 if self.action=='laptop' else 0
        delay=100 if self.action=='incense' else 140
        self.root.after(delay,self.tick)

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=ROOT)
    p.add_argument('--size',type=int,default=216);p.add_argument('--test-seconds',type=float,default=0)
    p.add_argument('--status',action='store_true');args=p.parse_args()
    if args.status:
        w=Watcher(args.workspace);print(json.dumps({'state':w.poll(),'error':w.error,'sessions':len(w.tails)},ensure_ascii=False));return
    Pet(args)

if __name__=='__main__':main()
