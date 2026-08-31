from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class Listing:
    seller_id:str; marketplace_id:str; sku:str; asin:str|None=None; title:str|None=None; brand:str|None=None; product_type:str|None=None; condition:str|None=None; listing_status:str|None=None; price:str|None=None; currency:str|None=None; fulfillment_channel:str|None=None; images:tuple[str,...]=(); bullet_points:tuple[str,...]=(); browse_nodes:tuple[str,...]=(); package_dimensions:dict|None=None
    def public_dict(self): return asdict(self)
    @classmethod
    def from_amazon(cls,raw,seller_id,marketplace_id):
        summary=raw.get("summaries",[{}]); summary=summary[0] if summary and isinstance(summary[0],dict) else {}; attributes=raw.get("attributes",{}) if isinstance(raw.get("attributes",{}),dict) else {}; offers=raw.get("offers",[{}]); offer=offers[0] if offers and isinstance(offers[0],dict) else {}; price=offer.get("price",{}) if isinstance(offer.get("price",{}),dict) else {}
        first=lambda value: value[0] if isinstance(value,list) and value and isinstance(value[0],str) else (value if isinstance(value,str) else None)
        strings=lambda value: tuple(item for item in value if isinstance(item,str)) if isinstance(value,list) else ()
        return cls(seller_id,marketplace_id,raw.get("sku") if isinstance(raw.get("sku"),str) else "",summary.get("asin") or raw.get("asin"),first(attributes.get("item_name")) or summary.get("itemName"),first(attributes.get("brand")),summary.get("productType"),summary.get("conditionType"),first(summary.get("status")),price.get("amount"),price.get("currencyCode"),summary.get("fulfillmentChannel"),strings(attributes.get("images")),strings(attributes.get("bullet_point")),strings(attributes.get("recommended_browse_nodes")),None)
