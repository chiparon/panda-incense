import argparse, types, unittest, time
from unittest.mock import patch
from pathlib import Path
import tkinter
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deskpet import Pet, ROOT

class UITest(unittest.TestCase):
    def test_real_tk_click_drag_and_resume(self):
        with patch.object(tkinter.Tk,'mainloop',lambda self:None):
            pet=Pet(argparse.Namespace(size=216,workspace=ROOT,test_seconds=0))
        try:
            pet.root.update();pet.base='laptop';pet.set_action('laptop')
            pet.canvas.event_generate('<ButtonPress-1>',x=100,y=100)
            pet.canvas.event_generate('<ButtonRelease-1>',x=100,y=100)
            pet.root.update();self.assertEqual(pet.action,'laugh')
            pet.override_until=0;pet.tick();self.assertEqual(pet.action,'laptop')
            pet.canvas.event_generate('<ButtonPress-1>',x=100,y=100)
            pet.canvas.event_generate('<B1-Motion>',x=120,y=100)
            pet.root.update();self.assertEqual(pet.action,'roll-right')
            pet.canvas.event_generate('<ButtonRelease-1>',x=120,y=100)
            self.assertEqual(pet.action,'roll-right')
            # Render the real transparent window on a neutral backing for visual QA.
            pet.drag=None;pet.play('laptop',10);pet.frame=4;pet.tick();pet.root.update()
            from PIL import ImageGrab
            x,y=pet.root.winfo_x(),pet.root.winfo_y()
            ImageGrab.grab((x,y,x+pet.size,y+pet.height)).save(ROOT/'assets/runtime-capture.png')
        finally:pet.root.destroy()

if __name__=='__main__':unittest.main()
