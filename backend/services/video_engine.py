from __future__ import annotations
import asyncio,re,tempfile,textwrap,uuid
from pathlib import Path
from typing import Any
import httpx
from PIL import Image,ImageDraw,ImageFont
from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.url_safety import validate_public_http_url
WIDTH,HEIGHT=1080,1920
def _font(size:int):
 for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","C:/Windows/Fonts/arialbd.ttf"):
  if Path(f).exists():return ImageFont.truetype(f,size)
 return ImageFont.load_default()
def _caption_image(text:str)->Image.Image:
 image=Image.new("RGBA",(WIDTH,320),(0,0,0,0));d=ImageDraw.Draw(image);font=_font(60);lines="\n".join(textwrap.wrap(text,24)[:3]) or " ";box=d.multiline_textbbox((0,0),lines,font=font,align="center",spacing=10);tw,th=box[2]-box[0],box[3]-box[1];x=(WIDTH-tw)//2;y=(320-th)//2;d.rounded_rectangle((x-28,y-22,x+tw+28,y+th+22),radius=24,fill=(15,23,42,220));d.multiline_text((x,y),lines,font=font,fill="white",align="center",spacing=10,stroke_width=1,stroke_fill="#0f172a");return image
async def _download_pexels(query:str,target:Path)->dict[str,Any]:
 key=get_settings().pexels_api_key
 if not key:raise IntegrationNotConfiguredError("PEXELS_API_KEY required to download background B-roll")
 async with httpx.AsyncClient(timeout=httpx.Timeout(30,connect=5),follow_redirects=False) as c:
  r=await c.get("https://api.pexels.com/videos/search",params={"query":query,"orientation":"portrait","per_page":10},headers={"Authorization":key});r.raise_for_status();videos=r.json().get("videos",[]);options=[]
  for video in videos:
   for f in video.get("video_files",[]):
    if f.get("file_type")=="video/mp4" and str(f.get("link","")).startswith("https://"):
     w,h=int(f.get("width") or 0),int(f.get("height") or 0)
     if w and h:options.append((abs(w/h-9/16)+abs(w-1080)/10000,video,f))
  if not options:raise RuntimeError("No usable Pexels MP4 files returned")
  _,video,file=min(options,key=lambda x:x[0]);url=await validate_public_http_url(file["link"]);size=0
  async with c.stream("GET",url,follow_redirects=False) as r:
   r.raise_for_status()
   with target.open("wb") as out:
    async for chunk in r.aiter_bytes():
     size+=len(chunk)
     if size>150*1024*1024:raise RuntimeError("B-roll asset exceeded 150 MB")
     out.write(chunk)
  return {"provider":"pexels","video_id":video.get("id"),"source_url":video.get("url"),"source_dimensions":{"width":file.get("width"),"height":file.get("height")}}
async def render_vertical_video(script:str,*,broll_query:str,output_path:str|None=None,voice:str="en-US-AriaNeural",captions:bool=True)->dict[str,Any]:
 if not script.strip() or not broll_query.strip():raise ValueError("script and broll_query required")
 try:import edge_tts;from moviepy import AudioFileClip,CompositeVideoClip,ImageClip,VideoFileClip,concatenate_videoclips
 except ImportError as exc:raise RuntimeError("Install MoviePy 2, edge-tts and Pillow") from exc
 s=get_settings();outdir=Path(s.video_output_dir).resolve();outdir.mkdir(parents=True,exist_ok=True);out=Path(output_path).resolve() if output_path else outdir/f"affiliate-os-{uuid.uuid4().hex}.mp4";out.parent.mkdir(parents=True,exist_ok=True);spoken=re.sub(r"\[[^]]*(?:visual|caption|b-roll|scene|on-screen)[^]]*\]","",script,flags=re.I);spoken=re.sub(r"\s+"," ",spoken).strip()
 if not spoken:raise ValueError("script contains no narration")
 segments=[x.strip() for x in re.split(r"(?<=[.!?])\s+",spoken) if x.strip()]
 with tempfile.TemporaryDirectory(prefix="affiliate-os-video-") as t:
  aud=Path(t)/"voice.mp3";bg=Path(t)/"broll.mp4";await edge_tts.Communicate(spoken,voice).save(str(aud));meta=await _download_pexels(broll_query,bg);clips=[];audio=None;original=None;resized=None;cropped=None;loop=[];layers=[];caption_clips=[];composite=None
  try:
   audio=AudioFileClip(str(aud));original=VideoFileClip(str(bg),audio=False);resized=original.resized(height=HEIGHT)
   if resized.w<WIDTH:resized=original.resized(width=WIDTH)
   cropped=resized.cropped(width=WIDTH,height=HEIGHT,x_center=resized.w/2,y_center=resized.h/2);duration=float(audio.duration)
   if cropped.duration>=duration:background=cropped.subclipped(0,duration);clips.append(background)
   else:
    remain=duration
    while remain>0:part=cropped.subclipped(0,min(cropped.duration,remain));loop.append(part);remain-=part.duration
    background=concatenate_videoclips(loop,method="compose").with_duration(duration);clips.extend(loop)
   layers=[background]
   if captions:
    total=max(1,len(spoken.split()));elapsed=0.0
    for sentence in segments:
     dur=min(max(.7,duration*len(sentence.split())/total),max(0,duration-elapsed))
     if dur<=0:break
     img=ImageClip(_caption_image(sentence)).with_start(elapsed).with_duration(dur).with_position((0,"center"));caption_clips.append(img);layers.append(img);elapsed+=dur
   composite=CompositeVideoClip(layers,size=(WIDTH,HEIGHT)).with_duration(duration).with_audio(audio);await asyncio.to_thread(composite.write_videofile,str(out),fps=30,codec="libx264",audio_codec="aac",preset="medium",threads=2,logger=None)
  finally:
   for clip in [composite,*caption_clips,*clips,*loop,cropped,resized,original,audio]:
    if clip is not None:
     try:clip.close()
     except Exception:pass
 if not out.exists() or out.stat().st_size==0:raise RuntimeError("Rendering completed without a non-empty output")
 return {"status":"rendered","path":str(out),"width":WIDTH,"height":HEIGHT,"aspect_ratio":"9:16","duration_seconds":round(duration,2),"voice":voice,"background_source":meta,"bytes":out.stat().st_size,"requires_license_review":True}
