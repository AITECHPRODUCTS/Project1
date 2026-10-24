from __future__ import annotations
import argparse,hashlib,os,re
from pathlib import Path
from typing import Any
COLLECTION_NAME="affiliate_doctrine"
REQUIRED_REFERENCES={"offer-frameworks.md","platform-rules.md","seo-strategy.md","social-data-providers.md"}
EXCLUDED_PARTS={"node_modules",".git",".next","dist","build","__pycache__"}
def find_markdown_files(repository:Path)->list[Path]:
 roots=[repository/"shared"/"references",repository/"skills"];files:set[Path]=set()
 for root in roots:
  if root.exists():files.update(root.rglob("*.md"))
 files.update(p for p in repository.glob("*.md") if p.is_file())
 return sorted(p for p in files if p.is_file() and p.stat().st_size and not any(part in EXCLUDED_PARTS for part in p.parts))
def split_markdown(path:Path,repository:Path,chunk_size:int=1200,overlap:int=180)->list[Any]:
 try:
  from langchain_core.documents import Document
  from langchain_text_splitters import MarkdownHeaderTextSplitter,RecursiveCharacterTextSplitter
 except ImportError as exc:raise RuntimeError("Install requirements.txt to use RAG ingestion") from exc
 text=path.read_text(encoding="utf-8",errors="replace").replace("\x00","");text=re.sub(r"\n{4,}","\n\n\n",text).strip()
 if not text:return []
 relative=path.relative_to(repository).as_posix();headers=MarkdownHeaderTextSplitter(headers_to_split_on=[("#","h1"),("##","h2"),("###","h3")],strip_headers=False);sections=headers.split_text(text)
 splitter=RecursiveCharacterTextSplitter(chunk_size=chunk_size,chunk_overlap=overlap,add_start_index=True,separators=["\n\n","\n",". "," ",""]);chunks=splitter.split_documents(sections or [Document(page_content=text)]);results=[]
 for i,chunk in enumerate(chunks):
  content=chunk.page_content.strip()
  if not content:continue
  heading=" | ".join(f"{k}: {chunk.metadata[k]}" for k in ("h1","h2","h3") if chunk.metadata.get(k));full=f"Source path: {relative}\nSection: {heading or 'document'}\n\n{content}";digest=hashlib.sha256(f"{relative}:{i}:{full}".encode()).hexdigest()
  results.append(Document(page_content=full,metadata={"source":relative,"chunk_index":i,"content_hash":digest,"document_kind":"skill" if relative.startswith("skills/") else "reference",**{k:v for k,v in chunk.metadata.items() if k in {"h1","h2","h3"}}}))
 return results
def build_documents(repository:Path,chunk_size:int=1200,overlap:int=180)->list[Any]:
 if not repository.is_dir():raise FileNotFoundError(f"Skill repository not found: {repository}")
 ref_dir=repository/"shared"/"references";missing=sorted(name for name in REQUIRED_REFERENCES if not (ref_dir/name).is_file())
 if missing:raise FileNotFoundError(f"Required reference file(s) missing from {ref_dir}: {', '.join(missing)}")
 docs=[doc for path in find_markdown_files(repository) for doc in split_markdown(path,repository,chunk_size,overlap)]
 if not docs:raise RuntimeError("No non-empty markdown documents found")
 return docs
def ingest(repository:Path,persist_directory:Path,embedding_model:str="sentence-transformers/all-MiniLM-L6-v2",chunk_size:int=1200,overlap:int=180,collection_name:str=COLLECTION_NAME)->dict[str,Any]:
 try:
  from langchain_chroma import Chroma
  from langchain_huggingface import HuggingFaceEmbeddings
 except ImportError as exc:raise RuntimeError("Install requirements.txt to use ChromaDB and HuggingFace embeddings") from exc
 if chunk_size<200 or overlap<0 or overlap>=chunk_size:raise ValueError("Require chunk_size >= 200 and 0 <= overlap < chunk_size")
 docs=build_documents(repository,chunk_size,overlap);persist_directory.mkdir(parents=True,exist_ok=True);embeddings=HuggingFaceEmbeddings(model_name=embedding_model,model_kwargs={"device":os.getenv("EMBEDDING_DEVICE","cpu")},encode_kwargs={"normalize_embeddings":True});store=Chroma(collection_name=collection_name,persist_directory=str(persist_directory),embedding_function=embeddings);ids=[doc.metadata["content_hash"] for doc in docs]
 for offset in range(0,len(docs),64):store.add_documents(docs[offset:offset+64],ids=ids[offset:offset+64])
 stale=[];existing=store._collection.get(include=["metadatas"])
 for doc_id,metadata in zip(existing.get("ids",[]),existing.get("metadatas",[])):
  if isinstance(metadata,dict) and metadata.get("document_kind") in {"skill","reference"} and doc_id not in set(ids):stale.append(doc_id)
 for offset in range(0,len(stale),64):store._collection.delete(ids=stale[offset:offset+64])
 return {"repository":str(repository.resolve()),"persist_directory":str(persist_directory.resolve()),"collection":collection_name,"chunks_processed":len(docs),"collection_count":int(store._collection.count()),"markdown_files":len(find_markdown_files(repository)),"stale_chunks_deleted":len(stale)}
def main()->None:
 p=argparse.ArgumentParser(description="Ingest licensed affiliate doctrine into local ChromaDB");p.add_argument("--repository",default=os.getenv("AFFILIATE_SKILLS_DIR","./knowledge/affiliate-skills"));p.add_argument("--persist-directory",default=os.getenv("CHROMA_PERSIST_DIR","./storage/chroma"));p.add_argument("--embedding-model",default=os.getenv("EMBEDDING_MODEL","sentence-transformers/all-MiniLM-L6-v2"));p.add_argument("--chunk-size",type=int,default=1200);p.add_argument("--overlap",type=int,default=180);a=p.parse_args();import json
 print(json.dumps(ingest(Path(a.repository),Path(a.persist_directory),a.embedding_model,a.chunk_size,a.overlap),indent=2))
if __name__=="__main__":main()
