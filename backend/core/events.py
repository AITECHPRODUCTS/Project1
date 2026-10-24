from __future__ import annotations
import asyncio,json,logging
from typing import Any
from fastapi import WebSocket
logger=logging.getLogger(__name__)
class EventHub:
 def __init__(self):self.connections:set[WebSocket]=set();self.lock=asyncio.Lock();self.redis=None;self.pubsub=None;self.listener=None;self.channel="affiliate_os:events:v1"
 async def start(self,url:str):
  try:
   from redis.asyncio import Redis
   redis=Redis.from_url(url,decode_responses=True,socket_connect_timeout=2,socket_timeout=2);await redis.ping();ps=redis.pubsub();await ps.subscribe(self.channel);self.redis,self.pubsub=redis,ps;self.listener=asyncio.create_task(self._listen());return True
  except Exception as exc:logger.warning("Redis event fanout disabled: %s",type(exc).__name__);return False
 async def _listen(self):
  try:
   async for msg in self.pubsub.listen():
    if msg.get("type")=="message":
     try:await self._deliver(json.loads(msg["data"]),publish=False)
     except (ValueError,TypeError,KeyError):logger.warning("Malformed Redis event ignored")
  except asyncio.CancelledError:raise
  except Exception as exc:logger.error("Redis event listener ended: %s",type(exc).__name__)
 async def connect(self,ws:WebSocket):
  await ws.accept()
  async with self.lock:self.connections.add(ws)
 async def disconnect(self,ws:WebSocket):
  async with self.lock:self.connections.discard(ws)
 async def _deliver(self,payload:dict[str,Any],publish:bool):
  message=json.dumps(payload,default=str)
  async with self.lock:connections=list(self.connections)
  dead=[]
  for ws in connections:
   try:await ws.send_text(message)
   except Exception:dead.append(ws)
  if dead:
   async with self.lock:
    for ws in dead:self.connections.discard(ws)
  if publish and self.redis:
   try:await self.redis.publish(self.channel,message)
   except Exception as exc:logger.warning("Redis event publish failed: %s",type(exc).__name__)
 async def publish(self,payload:dict[str,Any]):await self._deliver(payload,publish=True)
 async def stop(self):
  if self.listener:self.listener.cancel()
  if self.pubsub:await self.pubsub.aclose()
  if self.redis:await self.redis.aclose()
hub=EventHub()
