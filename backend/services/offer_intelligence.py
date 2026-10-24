from __future__ import annotations
from typing import Any
def compute_offer_metrics(offer:dict[str,Any],*,clicks:int|None=None,conversions:int|None=None,total_revenue:float|None=None,gravity_weight:float=1.0)->dict[str,Any]:
 if not 0<=gravity_weight<=10:raise ValueError("gravity_weight must be 0..10")
 clicks=max(0,int(clicks)) if clicks is not None else None;conversions=max(0,int(conversions)) if conversions is not None else None
 if clicks is not None and conversions is not None and conversions>clicks:raise ValueError("conversions cannot exceed clicks")
 revenue=max(0,float(total_revenue)) if total_revenue is not None else None;epc=revenue/clicks if revenue is not None and clicks else (0.0 if revenue==0 and clicks else None);cr=conversions/clicks if conversions is not None and clicks else (0.0 if conversions==0 and clicks else None)
 try:gravity=float(offer["gravity_score"]) if offer.get("gravity_score") is not None else None
 except (ValueError,TypeError):gravity=None
 if gravity is not None and gravity<0:gravity=None
 reward_type=str(offer.get("reward_type") or "").lower()
 return {"gravity_score":gravity,"normalized_gravity":gravity*gravity_weight if gravity is not None else None,"epc":round(epc,6) if epc is not None else None,"conversion_rate":round(cr,6) if cr is not None else None,"recurring_commission":("recurr" in reward_type or offer.get("recurring_commission") is True),"recurring_commission_value":offer.get("reward_value") if "recurr" in reward_type else None,"measurement_basis":{"clicks":clicks,"conversions":conversions,"total_revenue":revenue,"gravity_weight":gravity_weight}}
