from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=("ai_memory/ingester.py","ai_memory/rag_chain.py","ai_memory/training/prepare_dataset.py","ai_memory/training/train_lora.py","backend/main.py","backend/models.py","backend/workflows.py","backend/tools/affiliate_api.py","backend/services/s1_research.py","backend/services/s2_s3_content.py","backend/services/s4_s5_landing.py","backend/services/s6_s8_analytics.py","backend/services/video_engine.py","backend/core/state_machine.py","backend/core/middleware.py","frontend/app/page.tsx","frontend/components/FlywheelVisualizer.tsx","frontend/tailwind.config.js","Dockerfile","docker-compose.yml","README.md")
DOCTRINE=("offer-frameworks.md","platform-rules.md","seo-strategy.md","social-data-providers.md")
def main()->int:
 errors=[]
 for item in REQUIRED:
  if not (ROOT/item).is_file():errors.append(f"missing file {item}")
 root=ROOT/"knowledge/affiliate-skills"
 for name in DOCTRINE:
  if not (root/"shared/references"/name).is_file():errors.append(f"missing doctrine {name}")
 if not (root/"LICENSE").is_file():errors.append("missing source LICENSE")
 skills=list((root/"skills").rglob("SKILL.md")) if (root/"skills").exists() else []
 if len(skills)<52:errors.append(f"expected at least 52 skills, found {len(skills)}")
 python_files=list((ROOT/"backend").rglob("*.py"))+list((ROOT/"ai_memory").rglob("*.py"))+list((ROOT/"tests").rglob("*.py"))+list((ROOT/"scripts").rglob("*.py"))
 for p in python_files:
  try:ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
  except (SyntaxError,UnicodeError) as exc:errors.append(f"Python syntax error {p.relative_to(ROOT)}: {exc}")
 tw=(ROOT/"frontend/tailwind.config.js").read_text(encoding="utf-8") if (ROOT/"frontend/tailwind.config.js").exists() else ""
 if "8px 8px 16px #d1d9e6, -8px -8px 16px #ffffff" not in tw:errors.append("required exact 3d-light shadow missing")
 css=(ROOT/"frontend/app/globals.css").read_text(encoding="utf-8") if (ROOT/"frontend/app/globals.css").exists() else ""
 for c in ("#f8fafc","#ffffff","#1e293b","#6366f1"):
  if c not in css:errors.append(f"palette color missing {c}")
 configs=(ROOT/"config.yaml").read_text(encoding="utf-8") if (ROOT/"config.yaml").exists() else ""
 network_count=sum(1 for line in configs.splitlines() if line.startswith("  ") and ": {enabled:" in line)
 if network_count<100:errors.append(f"catalog should have >=100 network entries, found {network_count}")
 if errors:
  print("STATIC VERIFICATION FAILED")
  for item in errors:print("-",item)
  return 1
 print("STATIC VERIFICATION PASSED");print(f"Python source files parsed: {len(python_files)}");print(f"Skill files: {len(skills)}");print(f"Affiliate network catalogue entries (mostly disabled): {network_count}");print(f"Required doctrine files: {len(DOCTRINE)}")
 return 0
if __name__=="__main__":raise SystemExit(main())
