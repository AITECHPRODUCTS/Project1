from __future__ import annotations
import asyncio,json,math,re,tempfile,textwrap,uuid
from pathlib import Path
from typing import Any
from PIL import Image,ImageDraw,ImageFont
from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.url_safety import declared_content_length,open_public_http_response,read_limited_response
WIDTH,HEIGHT=1080,1920
MAX_PEXELS_SEARCH_BYTES=2*1024*1024
MAX_BROLL_DOWNLOAD_BYTES=150*1024*1024
MAX_BROLL_DURATION_SECONDS=180.0
MAX_RENDER_DURATION_SECONDS=180.0
MAX_RENDER_OUTPUT_BYTES=500*1024*1024

def _font(size:int):
 for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","C:/Windows/Fonts/arialbd.ttf"):
  if Path(f).exists():return ImageFont.truetype(f,size)
 return ImageFont.load_default()

def _caption_image(text:str)->Image.Image:
 image=Image.new("RGBA",(WIDTH,320),(0,0,0,0));d=ImageDraw.Draw(image);font=_font(60);lines="\n".join(textwrap.wrap(text,24)[:3]) or " ";box=d.multiline_textbbox((0,0),lines,font=font,align="center",spacing=10);tw,th=box[2]-box[0],box[3]-box[1];x=(WIDTH-tw)//2;y=(320-th)//2;d.rounded_rectangle((x-28,y-22,x+tw+28,y+th+22),radius=24,fill=(15,23,42,220));d.multiline_text((x,y),lines,font=font,fill="white",align="center",spacing=10,stroke_width=1,stroke_fill="#0f172a");return image

def _bounded_duration(value:Any,*,label:str,max_seconds:float=MAX_RENDER_DURATION_SECONDS)->float:
 try:seconds=float(value)
 except (TypeError,ValueError) as exc:raise ValueError(f"{label} must be a finite positive duration") from exc
 if not math.isfinite(seconds) or seconds<=0 or seconds>max_seconds:
  raise ValueError(f"{label} must be between 0 and {max_seconds:g} seconds")
 return seconds

async def _download_pexels(query:str,target:Path)->dict[str,Any]:
 key=get_settings().pexels_api_key
 if not key:raise IntegrationNotConfiguredError("PEXELS_API_KEY required to download background B-roll")
 api_url="https://api.pexels.com/videos/search"
 async with open_public_http_response(api_url,method="GET",params={"query":query,"orientation":"portrait","per_page":10},headers={"Authorization":key,"Accept":"application/json"},timeout=20.0) as response:
  if 300<=response.status_code<400:raise ValueError("Pexels search redirect blocked")
  response.raise_for_status()
  media_type=response.headers.get("content-type","").split(";",1)[0].strip().lower()
  if media_type not in {"application/json","application/problem+json"}:raise ValueError(f"Unsupported Pexels search content type: {media_type or 'missing'}")
  payload=json.loads(await read_limited_response(response,max_bytes=MAX_PEXELS_SEARCH_BYTES))
 videos=payload.get("videos",[]) if isinstance(payload,dict) else []
 options=[]
 for item_video in videos if isinstance(videos,list) else []:
  if not isinstance(item_video,dict):continue
  try:source_duration=_bounded_duration(item_video.get("duration"),label="Pexels clip duration",max_seconds=MAX_BROLL_DURATION_SECONDS)
  except ValueError:continue
  for item_file in item_video.get("video_files") or []:
   if not isinstance(item_file,dict) or item_file.get("file_type")!="video/mp4":continue
   link=str(item_file.get("link",""))
   if not link.startswith("https://"):continue
   try:
    width,height=int(item_file.get("width") or 0),int(item_file.get("height") or 0)
    reported_size=int(item_file.get("size") or item_file.get("file_size") or 0)
   except (TypeError,ValueError):continue
   if width<=0 or height<=0 or reported_size<0 or reported_size>MAX_BROLL_DOWNLOAD_BYTES:continue
   options.append((abs(width/height-9/16)+abs(width-1080)/10000,item_video,item_file,source_duration))
 if not options:raise RuntimeError("No usable Pexels MP4 files within the supported duration and size limits")
 _,item_video,item_file,source_duration=min(options,key=lambda item:item[0])
 target.parent.mkdir(parents=True,exist_ok=True)
 url=str(item_file["link"])
 declared_size=None
 try:
  async with open_public_http_response(url,method="GET",headers={"Accept":"video/mp4,application/octet-stream"},timeout=90.0) as response:
   if 300<=response.status_code<400:raise ValueError("Pexels media redirect blocked; redirects are not followed")
   response.raise_for_status()
   media_type=response.headers.get("content-type","").split(";",1)[0].strip().lower()
   if media_type not in {"video/mp4","application/octet-stream"}:raise ValueError(f"Unsupported Pexels media content type: {media_type or 'missing'}")
   encoding=response.headers.get("content-encoding","identity").strip().lower()
   if encoding not in {"","identity"}:raise ValueError("Encoded Pexels media responses are not accepted")
   declared_size=declared_content_length(response,MAX_BROLL_DOWNLOAD_BYTES)
   size=0
   with target.open("wb") as output:
    async for chunk in response.aiter_raw():
     size+=len(chunk)
     if size>MAX_BROLL_DOWNLOAD_BYTES:raise ValueError("B-roll asset exceeded the 150 MiB byte limit")
     output.write(chunk)
  if size<=0:raise ValueError("Pexels returned an empty media asset")
  if declared_size is not None and declared_size!=size:raise ValueError("Pexels media size did not match Content-Length")
 except BaseException:
  target.unlink(missing_ok=True)
  raise
 return {"provider":"pexels","video_id":item_video.get("id"),"source_url":item_video.get("url"),"source_dimensions":{"width":item_file.get("width"),"height":item_file.get("height")},"source_duration_seconds":source_duration,"bytes":size}

async def render_vertical_video(script:str,*,broll_query:str,output_path:str|None=None,voice:str="en-US-AriaNeural",captions:bool=True)->dict[str,Any]:
 if not script.strip() or not broll_query.strip():raise ValueError("script and broll_query required")
 try:import edge_tts;from moviepy import AudioFileClip,CompositeVideoClip,ImageClip,VideoFileClip,concatenate_videoclips
 except ImportError as exc:raise RuntimeError("Install MoviePy 2, edge-tts and Pillow") from exc
 settings=get_settings();outdir=Path(settings.video_output_dir).resolve();outdir.mkdir(parents=True,exist_ok=True);out=Path(output_path).resolve() if output_path else outdir/f"affiliate-os-{uuid.uuid4().hex}.mp4"
 try:out.relative_to(outdir)
 except ValueError as exc:raise ValueError("Video output path must remain inside the configured video output directory") from exc
 out.parent.mkdir(parents=True,exist_ok=True);spoken=re.sub(r"\[[^]]*(?:visual|caption|b-roll|scene|on-screen)[^]]*\]","",script,flags=re.I);spoken=re.sub(r"\s+"," ",spoken).strip()
 if not spoken:raise ValueError("script contains no narration")
 segments=[x.strip() for x in re.split(r"(?<=[.!?])\s+",spoken) if x.strip()]
 with tempfile.TemporaryDirectory(prefix="affiliate-os-video-") as tempdir:
  audio_path=Path(tempdir)/"voice.mp3";broll_path=Path(tempdir)/"broll.mp4"
  await edge_tts.Communicate(spoken,voice).save(str(audio_path))
  clips=[];audio=None;original=None;resized=None;cropped=None;loop=[];layers=[];caption_clips=[];composite=None
  try:
   audio=AudioFileClip(str(audio_path));duration=_bounded_duration(audio.duration,label="Narration duration",max_seconds=MAX_RENDER_DURATION_SECONDS)
   meta=await _download_pexels(broll_query,broll_path)
   original=VideoFileClip(str(broll_path),audio=False)
   _bounded_duration(original.duration,label="Downloaded B-roll duration",max_seconds=MAX_BROLL_DURATION_SECONDS)
   resized=original.resized(height=HEIGHT)
   if resized.w<WIDTH:resized=original.resized(width=WIDTH)
   cropped=resized.cropped(width=WIDTH,height=HEIGHT,x_center=resized.w/2,y_center=resized.h/2)
   if cropped.duration>=duration:
    background=cropped.subclipped(0,duration);clips.append(background)
   else:
    remain=duration
    while remain>0:
     part=cropped.subclipped(0,min(cropped.duration,remain));loop.append(part);remain-=part.duration
    background=concatenate_videoclips(loop,method="compose").with_duration(duration);clips.extend(loop)
   layers=[background]
   if captions:
    total=max(1,len(spoken.split()));elapsed=0.0
    for sentence in segments:
     segment_duration=min(max(.7,duration*len(sentence.split())/total),max(0,duration-elapsed))
     if segment_duration<=0:break
     layer=ImageClip(_caption_image(sentence)).with_start(elapsed).with_duration(segment_duration).with_position((0,"center"));caption_clips.append(layer);layers.append(layer);elapsed+=segment_duration
   composite=CompositeVideoClip(layers,size=(WIDTH,HEIGHT)).with_duration(duration).with_audio(audio)
   await asyncio.to_thread(composite.write_videofile,str(out),fps=30,codec="libx264",audio_codec="aac",preset="medium",threads=2,logger=None)
  finally:
   for clip in [composite,*caption_clips,*clips,*loop,cropped,resized,original,audio]:
    if clip is not None:
     try:clip.close()
     except Exception:pass
 if not out.exists() or out.stat().st_size==0:raise RuntimeError("Rendering completed without a non-empty output")
 if out.stat().st_size>MAX_RENDER_OUTPUT_BYTES:
  out.unlink(missing_ok=True)
  raise ValueError("Rendered video exceeded the 500 MiB output byte limit")
 return {"status":"rendered","path":str(out),"width":WIDTH,"height":HEIGHT,"aspect_ratio":"9:16","duration_seconds":round(duration,2),"voice":voice,"background_source":meta,"bytes":out.stat().st_size,"requires_license_review":True}
