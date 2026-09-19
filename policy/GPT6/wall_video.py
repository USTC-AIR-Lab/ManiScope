"""Real elapsed-time recording, including frozen simulation during inference."""
import json,time,subprocess
from pathlib import Path
import cv2
import numpy as np
class WallVideo:
 def __init__(self,folder,rgb,fps=10):
  folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);self.fps=fps;self.start=time.monotonic();self.count=0;self.frame=np.asarray(rgb).copy();self.phase='initial';self.closed=False
  h,w=self.frame.shape[:2]
  self.process=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{h}','-framerate',str(fps),'-i','-','-pix_fmt','yuv420p','-vcodec','libx264','-preset','ultrafast','-crf','25','-movflags','frag_keyframe+empty_moov',str(folder/'wall_clock.mp4')],stdin=subprocess.PIPE)
  self.events=(folder/'wall_clock_events.jsonl').open('w')
 def push(self,rgb,phase):
  if self.closed:return
  elapsed=time.monotonic()-self.start;target=int(elapsed*self.fps)
  while self.count<target:
   frame=self.frame.copy();cv2.putText(frame,f'{self.count/self.fps:.1f}s  {self.phase}',(6,17),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,0),1)
   self.process.stdin.write(frame.tobytes());self.count+=1
  self.events.write(json.dumps({'elapsed_seconds':elapsed,'phase':phase,'encoded_frames':self.count})+'\n');self.events.flush()
  self.frame=np.asarray(rgb).copy();self.phase=phase
 def close(self):
  if self.closed:return
  self.push(self.frame,'finished');self.closed=True;self.process.stdin.close();self.process.wait();self.events.close()
