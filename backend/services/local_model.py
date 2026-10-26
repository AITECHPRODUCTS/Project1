from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any
@lru_cache(maxsize=1)
def _load(path:str,adapter:str,device_pref:str):
 try:import torch;from transformers import AutoModelForCausalLM,AutoTokenizer
 except ImportError as exc:raise RuntimeError("Install torch, transformers and accelerate; install peft for a LoRA adapter") from exc
 if not path:raise ValueError("LOCAL_MODEL_PATH is required")
 device=device_pref.lower();device=("cuda" if torch.cuda.is_available() else "cpu") if device=="auto" else device
 if device.startswith("cuda") and not torch.cuda.is_available():raise RuntimeError("CUDA requested but unavailable")
 tokenizer=AutoTokenizer.from_pretrained(path,use_fast=True,trust_remote_code=False,local_files_only=True)
 if tokenizer.pad_token is None:tokenizer.pad_token=tokenizer.eos_token
 model=AutoModelForCausalLM.from_pretrained(path,torch_dtype=torch.float16 if device.startswith("cuda") else torch.float32,low_cpu_mem_usage=True,trust_remote_code=False,local_files_only=True).to(device)
 if adapter:
  if not Path(adapter).exists():raise FileNotFoundError(f"LoRA adapter does not exist: {adapter}")
  try:from peft import PeftModel
  except ImportError as exc:raise RuntimeError("Install peft to load a LoRA adapter") from exc
  model=PeftModel.from_pretrained(model,adapter,is_trainable=False,local_files_only=True).to(device)
 model.eval();return tokenizer,model,device
def generate_local(*,model_path:str,adapter_path:str,device_preference:str,system_prompt:str,user_prompt:str,max_new_tokens:int,temperature:float)->str:
 import torch
 tok,model,device=_load(model_path,adapter_path,device_preference);messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}]
 prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True) if getattr(tok,"chat_template",None) else f"SYSTEM:\n{system_prompt}\nUSER:\n{user_prompt}\nASSISTANT:"
 inputs=tok(prompt,return_tensors="pt",truncation=True,max_length=8192);inputs={k:v.to(device) for k,v in inputs.items()};start=inputs["input_ids"].shape[1]
 opts:dict[str,Any]={"max_new_tokens":max(1,min(max_new_tokens,4096)),"pad_token_id":tok.pad_token_id,"eos_token_id":tok.eos_token_id,"do_sample":temperature>0}
 if temperature>0:opts.update(temperature=min(max(temperature,.05),1.5),top_p=.9)
 with torch.inference_mode():out=model.generate(**inputs,**opts)
 text=tok.decode(out[0][start:],skip_special_tokens=True).strip()
 if not text:raise RuntimeError("Local model returned empty output")
 return text
