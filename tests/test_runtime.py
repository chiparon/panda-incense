import json, tempfile, unittest, sqlite3
from pathlib import Path
import sys
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deskpet import EventTail, Watcher

class RuntimeTest(unittest.TestCase):
    def test_partial_lines_and_transition(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'events';p.write_text('');t=EventTail(p)
            def append(typ):
                with p.open('a') as f:f.write(json.dumps({'type':'event_msg','payload':{'type':typ}})+'\n')
                t.poll()
            append('task_started');self.assertEqual(t.state,'laptop')
            with p.open('a') as f:f.write('{"type":"event_msg","payload":{"type":"task_complete"}}')
            t.poll();self.assertEqual(t.state,'laptop')
            with p.open('a') as f:f.write('\n')
            t.poll();self.assertEqual(t.state,'review')
            append('turn_aborted');self.assertEqual(t.state,'recover')
    def test_workspace_priority_and_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);db=root/'state_5.sqlite'
            with closing(sqlite3.connect(db)) as c:
                c.execute('CREATE TABLE threads(id,rollout_path,cwd,archived,updated_at)')
                for i,(kind,workspace) in enumerate([('task_started','\\\\?\\E:\\project'),('task_complete','E:/project'),('task_started','E:/other')]):
                    p=root/f'{i}.jsonl';p.write_text(json.dumps({'type':'event_msg','timestamp':str(i),'payload':{'type':kind}})+'\n')
                    c.execute('INSERT INTO threads VALUES(?,?,?,?,?)',(str(i),str(p),workspace,0,i))
                c.commit()
            w=Watcher('E:\\project',root);self.assertEqual(w.poll(),'laptop');self.assertEqual(len(w.tails),2)
            self.assertIsNone(w.error)

if __name__=='__main__':unittest.main()
