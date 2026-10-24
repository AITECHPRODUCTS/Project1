from __future__ import annotations
from abc import ABC,abstractmethod
from typing import Any
class AffiliateNetworkAdapter(ABC):
 network_name:str
 @abstractmethod
 async def fetch_offers(self,*,query:str|None=None,limit:int=100)->list[dict[str,Any]]:...
 @abstractmethod
 def parse_conversion(self,payload:dict[str,Any])->dict[str,Any]:...
