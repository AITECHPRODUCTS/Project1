from __future__ import annotations
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=("backend/main.py","backend/models.py","backend/schemas.py","backend/database.py","backend/workflows.py","backend/core/state_machine.py","backend/core/middleware.py","backend/tools/affiliate_api.py","backend/services/s1_research.py","backend/services/s2_s3_content.py","backend/services/s4_s5_landing.py","backend/services/s6_s8_analytics.py","backend/services/video_engine.py","backend/services/tracking_service.py","backend/services/integration_registry.py","backend/services/llm.py","ai_memory/ingester.py","ai_memory/rag_chain.py","frontend/app/page.tsx","frontend/components/FlywheelVisualizer.tsx","config.yaml","requirements.txt","README.md")
def main()->int:
 errors=[]
 for item in REQUIRED:
  if not (ROOT/item).is_file():errors.append(f"missing required source {item}")
 py=list((ROOT/"backend").rglob("*.py"))+list((ROOT/"ai_memory").rglob("*.py"))+list((ROOT/"tests").rglob("*.py"))+list((ROOT/"scripts").rglob("*.py"))
 for p in py:
  try:ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
  except (SyntaxError,UnicodeError) as e:errors.append(f"syntax error {p.relative_to(ROOT)}: {e}")
 cfg=(ROOT/"config.yaml").read_text(encoding="utf-8") if (ROOT/"config.yaml").exists() else ""
 network_count=sum(1 for line in cfg.splitlines() if line.startswith("  ") and ": {enabled:" in line)
 if network_count<100:errors.append(f"provider catalogue contains only {network_count} entries; expected at least 100 catalogued entries")
 matrix=ROOT/"docs/skill-parity-matrix.csv"
 if not matrix.is_file():errors.append("missing docs/skill-parity-matrix.csv; do not imply all 53 skills are implemented")
 if matrix.is_file():
  rows=[x for x in matrix.read_text(encoding="utf-8").splitlines() if x and not x.startswith("skill_id,")]
  if len(rows)!=53:errors.append(f"skill parity matrix should have 53 explicit entries, found {len(rows)}")
 css=(ROOT/"frontend/app/globals.css").read_text(encoding="utf-8") if (ROOT/"frontend/app/globals.css").exists() else ""
 for color in ("#f8fafc","#1e293b","#6366f1"):
  if color not in css:errors.append(f"design palette missing {color}")
 if "#fff" not in css and "#ffffff" not in css:errors.append("design surface color missing (#fff/#ffffff)")
 tw=(ROOT/"frontend/tailwind.config.js").read_text(encoding="utf-8") if (ROOT/"frontend/tailwind.config.js").exists() else ""
 if "8px 8px 16px #d1d9e6, -8px -8px 16px #ffffff" not in tw:errors.append("3D light shadow token missing")
 root=ROOT/"knowledge/affiliate-skills/shared/references"
 for name in ("offer-frameworks.md","platform-rules.md","seo-strategy.md","social-data-providers.md"):
  if not (root/name).is_file():errors.append(f"required RAG reference missing: {name}")
 if not (ROOT/"knowledge/affiliate-skills/LICENSE").is_file():errors.append("upstream skill license/provenance missing")
 if errors:
  print("STATIC VERIFICATION FAILED")
  for item in errors:print("-",item)
  return 1
 print("STATIC VERIFICATION PASSED");print(f"Python files parsed: {len(py)}");print(f"Affiliate/network catalogue entries: {network_count}");print("Skill matrix entries: 53 (statuses explicit; not a claim of full parity)")
 return 0
if __name__=="__main__":raise SystemExit(main())
