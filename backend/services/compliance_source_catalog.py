from __future__ import annotations

import re
from typing import Any

from backend.services.jurisdiction_compliance import REQUIRED_RULE_CATEGORIES, normalize_jurisdictions


CATALOG_PREPARED_AT = "2026-10-28"
GLOBAL = "GLOBAL"

# These entries are pointers to official legislation, regulators, self-regulatory
# bodies, or platform policy pages. They are not pre-approved legal evidence.
# Keep scope codes exact: a GLOBAL policy and an EU reference must not silently
# satisfy US/GB/IN/CA/AU or other country-specific evidence requirements.
SOURCE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "source_id": "us-ftc-endorsements",
        "jurisdiction_code": "US",
        "authority": "U.S. Federal Trade Commission",
        "title": "Endorsements, Influencers, and Reviews",
        "url": "https://www.ftc.gov/business-guidance/advertising-marketing/endorsements-influencers-reviews",
        "source_type": "regulator_guidance",
        "categories": ["affiliate_disclosure", "advertising_claims", "consumer_protection"],
        "activities": ["affiliate_promotion", "content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "Official FTC guidance on endorsements, influencer marketing and reviews. Review the current Endorsement Guides and any product-specific rules relevant to the campaign.",
    },
    {
        "source_id": "us-ftc-disclosures-social",
        "jurisdiction_code": "US",
        "authority": "U.S. Federal Trade Commission",
        "title": "Disclosures 101 for Social Media Influencers",
        "url": "https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers",
        "source_type": "regulator_guidance",
        "categories": ["affiliate_disclosure"],
        "activities": ["affiliate_promotion", "content_publish", "merchant_marketplace"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "Official FTC disclosure guidance. Confirm how prominence, placement, format and the audience's context apply to the exact creative and channel.",
    },
    {
        "source_id": "us-ftc-can-spam",
        "jurisdiction_code": "US",
        "authority": "U.S. Federal Trade Commission",
        "title": "CAN-SPAM Act: A Compliance Guide for Business",
        "url": "https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business",
        "source_type": "regulator_guidance",
        "categories": ["email_marketing", "consent_and_marketing"],
        "activities": ["email_marketing"],
        "channels": ["email", "email_marketing"],
        "source_updated_at": None,
        "scope_note": "Official FTC guidance for commercial email. Confirm applicability to the sender, message type, recipient and current law before relying on it.",
    },
    {
        "source_id": "gb-cap-section-2",
        "jurisdiction_code": "GB",
        "authority": "Advertising Standards Authority / Committee of Advertising Practice",
        "title": "CAP Code Section 2 — Recognition of Marketing Communications",
        "url": "https://www.asa.org.uk/type/non_broadcast/code_section/02.html",
        "source_type": "self_regulatory_code",
        "categories": ["affiliate_disclosure", "advertising_claims", "consumer_protection"],
        "activities": ["affiliate_promotion", "content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "Official UK advertising-code text on recognition of marketing communications. Review applicable product, audience and media sections as well as legislation.",
    },
    {
        "source_id": "gb-asa-recognising-social-ads",
        "jurisdiction_code": "GB",
        "authority": "Advertising Standards Authority / Committee of Advertising Practice",
        "title": "Recognising Ads: Social Media and Influencer Marketing",
        "url": "https://www.asa.org.uk/advice-online/recognising-ads-social-media.html",
        "source_type": "regulator_guidance",
        "categories": ["affiliate_disclosure", "advertising_claims"],
        "activities": ["affiliate_promotion", "content_publish", "paid_media"],
        "channels": ["any"],
        "source_updated_at": "2026-08-06",
        "scope_note": "ASA/CAP advice discusses affiliate and influencer content. The page itself notes it is advice and not a substitute for checking the applicable law and code.",
    },
    {
        "source_id": "gb-ico-pecr-electronic-marketing",
        "jurisdiction_code": "GB",
        "authority": "Information Commissioner's Office",
        "title": "PECR Guide — Electronic and Telephone Marketing",
        "url": "https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/",
        "source_type": "regulator_guidance",
        "categories": ["email_marketing", "consent_and_marketing", "privacy_data_protection", "cookie_tracking"],
        "activities": ["email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["email", "email_marketing", "web", "analytics"],
        "source_updated_at": "2025-08-20",
        "scope_note": "ICO guidance on electronic direct marketing and PECR. Confirm current updates, communication type, consent basis and any relevant UK GDPR duties.",
    },
    {
        "source_id": "in-asci-advertising-code",
        "jurisdiction_code": "IN",
        "authority": "Advertising Standards Council of India",
        "title": "ASCI Code Guidelines",
        "url": "https://www.ascionline.in/the-asci-code-guidelines/",
        "source_type": "self_regulatory_code",
        "categories": ["affiliate_disclosure", "advertising_claims", "consumer_protection"],
        "activities": ["affiliate_promotion", "content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "ASCI's advertising-code and influencer guidance is self-regulatory material. Also check applicable Indian legislation, sector rules and current ASCI updates.",
    },
    {
        "source_id": "in-dpdp-act",
        "jurisdiction_code": "IN",
        "authority": "Government of India — India Code",
        "title": "Digital Personal Data Protection Act, 2023",
        "url": "https://www.indiacode.nic.in/indiacode/handle/123456789/22037?view_type=browse",
        "source_type": "legislation",
        "categories": ["privacy_data_protection", "consent_and_marketing", "data_retention"],
        "activities": ["content_publish", "email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "Official Act text. The Act has a staged commencement framework; confirm which provisions are in force for the date and processing activity being assessed.",
    },
    {
        "source_id": "in-dpdp-rules-2025",
        "jurisdiction_code": "IN",
        "authority": "Ministry of Electronics and Information Technology, Government of India",
        "title": "Digital Personal Data Protection Rules, 2025 and implementation references",
        "url": "https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025%3B",
        "source_type": "regulation",
        "categories": ["privacy_data_protection", "consent_and_marketing", "data_retention"],
        "activities": ["content_publish", "email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["any"],
        "source_updated_at": "2025-12-16",
        "scope_note": "MeitY's official page lists the notified Rules, corrigendum and enforcement timeline. Check the applicable commencement dates; do not assume every substantive provision is already effective.",
    },
    {
        "source_id": "ca-competition-bureau-influencer",
        "jurisdiction_code": "CA",
        "authority": "Competition Bureau Canada",
        "title": "Influencer Marketing and the Competition Act",
        "url": "https://competition-bureau.canada.ca/en/deceptive-marketing-practices/types-deceptive-marketing-practices/influencer-marketing-and-competition-act",
        "source_type": "regulator_guidance",
        "categories": ["affiliate_disclosure", "advertising_claims", "consumer_protection"],
        "activities": ["affiliate_promotion", "content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "Official Competition Bureau guidance on material connections and influencer marketing. Review the current Competition Act and applicable provincial rules for the specific case.",
    },
    {
        "source_id": "ca-crtc-casl",
        "jurisdiction_code": "CA",
        "authority": "Canadian Radio-television and Telecommunications Commission",
        "title": "CASL Guidance on Implied Consent",
        "url": "https://crtc.gc.ca/eng/com500/guide.htm",
        "source_type": "regulator_guidance",
        "categories": ["email_marketing", "consent_and_marketing"],
        "activities": ["email_marketing"],
        "channels": ["email", "email_marketing"],
        "source_updated_at": None,
        "scope_note": "Official CRTC guidance on consent for commercial electronic messages. Confirm the sender's evidence of consent, required identification and unsubscribe handling.",
    },
    {
        "source_id": "au-oaic-app-guidelines",
        "jurisdiction_code": "AU",
        "authority": "Office of the Australian Information Commissioner",
        "title": "Australian Privacy Principles Guidelines",
        "url": "https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines",
        "source_type": "regulator_guidance",
        "categories": ["privacy_data_protection", "consent_and_marketing", "data_retention"],
        "activities": ["content_publish", "email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["any"],
        "source_updated_at": "2026-05-13",
        "scope_note": "OAIC guidance includes direct-marketing and cross-border privacy topics. Confirm the entity, information type, current APP text and applicable exceptions.",
    },
    {
        "source_id": "au-oaic-direct-marketing",
        "jurisdiction_code": "AU",
        "authority": "Office of the Australian Information Commissioner",
        "title": "Direct Marketing Privacy Guidance",
        "url": "https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/direct-marketing",
        "source_type": "regulator_guidance",
        "categories": ["email_marketing", "consent_and_marketing", "privacy_data_protection", "data_retention"],
        "activities": ["email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["email", "email_marketing", "web", "analytics"],
        "source_updated_at": None,
        "scope_note": "OAIC guidance explains Australian Privacy Principle 7 and interactions with other marketing laws. Check current Spam Act and Do Not Call obligations separately where relevant.",
    },
    {
        "source_id": "eu-unfair-commercial-practices",
        "jurisdiction_code": "EU",
        "authority": "European Union — EUR-Lex",
        "title": "Unfair Commercial Practices Directive (current consolidated text)",
        "url": "https://eur-lex.europa.eu/eli/dir/2005/29/oj",
        "source_type": "legislation",
        "categories": ["affiliate_disclosure", "advertising_claims", "consumer_protection"],
        "activities": ["affiliate_promotion", "content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["any"],
        "source_updated_at": "2026-09-27",
        "scope_note": "EUR-Lex displayed a consolidated version dated 27 September 2026 when this catalogue was prepared. Verify the latest version and national implementation for the target member state.",
    },
    {
        "source_id": "eu-gdpr",
        "jurisdiction_code": "EU",
        "authority": "European Union — EUR-Lex",
        "title": "General Data Protection Regulation (Regulation (EU) 2016/679)",
        "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "source_type": "legislation",
        "categories": ["privacy_data_protection", "consent_and_marketing", "data_retention"],
        "activities": ["content_publish", "email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["any"],
        "source_updated_at": None,
        "scope_note": "Official EU legal text. Confirm current amendments, territorial scope, local supervisory guidance and national law that applies to the activity.",
    },
    {
        "source_id": "eu-eprivacy",
        "jurisdiction_code": "EU",
        "authority": "European Union — EUR-Lex",
        "title": "Privacy and Electronic Communications Directive (2002/58/EC)",
        "url": "https://eur-lex.europa.eu/eli/dir/2002/58/oj",
        "source_type": "legislation",
        "categories": ["email_marketing", "consent_and_marketing", "cookie_tracking", "privacy_data_protection"],
        "activities": ["email_marketing", "lead_capture", "tracking_analytics"],
        "channels": ["email", "email_marketing", "web", "analytics"],
        "source_updated_at": None,
        "scope_note": "Official ePrivacy directive text. Member-state implementation and current national cookie/marketing guidance may add material requirements.",
    },
    {
        "source_id": "global-meta-ad-standards",
        "jurisdiction_code": "GLOBAL",
        "authority": "Meta Transparency Center",
        "title": "Meta Advertising Standards",
        "url": "https://transparency.meta.com/policies/ad-standards/",
        "source_type": "platform_policy",
        "categories": ["platform_terms", "paid_media_rules", "advertising_claims"],
        "activities": ["content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["meta", "facebook", "instagram"],
        "source_updated_at": None,
        "scope_note": "Platform policy only, not law. Meta also applies product-specific rules and local law; this GLOBAL entry cannot replace national or regional evidence.",
    },
    {
        "source_id": "global-google-misrepresentation",
        "jurisdiction_code": "GLOBAL",
        "authority": "Google Ads Policy Center",
        "title": "Google Ads Misrepresentation Policy",
        "url": "https://support.google.com/adspolicy/answer/6020955?hl=en",
        "source_type": "platform_policy",
        "categories": ["platform_terms", "paid_media_rules", "advertising_claims"],
        "activities": ["content_publish", "paid_media", "merchant_marketplace"],
        "channels": ["google_ads", "google_search", "google_display", "youtube", "youtube_shorts"],
        "source_updated_at": None,
        "scope_note": "Google Ads platform policy, not law. Review the account/product-specific policies and the actual landing destination; platform policy does not replace local law.",
    },
    {
        "source_id": "global-google-destination",
        "jurisdiction_code": "GLOBAL",
        "authority": "Google Ads Policy Center",
        "title": "Google Ads Destination Requirements",
        "url": "https://support.google.com/adspolicy/answer/6368661?hl=en",
        "source_type": "platform_policy",
        "categories": ["platform_terms", "paid_media_rules", "advertising_claims"],
        "activities": ["content_publish", "paid_media"],
        "channels": ["google_ads", "google_search", "google_display", "youtube", "youtube_shorts"],
        "source_updated_at": None,
        "scope_note": "Google Ads destination policy, not law. Check functional accessibility, destination consistency and account-specific requirements for each actual campaign.",
    },
)

_ALLOWED_CATEGORIES = {
    category for categories in REQUIRED_RULE_CATEGORIES.values() for category in categories
}
_ALLOWED_ACTIVITIES = set(REQUIRED_RULE_CATEGORIES)


def get_compliance_source_catalog(
    *,
    jurisdiction: str,
    category: str | None = None,
    activity: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Find curated official references without claiming they establish compliance."""
    requested_jurisdiction = normalize_jurisdictions([jurisdiction])[0]
    normalized_category = str(category or "").strip().lower() or None
    normalized_activity = str(activity or "").strip().lower() or None
    normalized_channel = str(channel or "").strip().lower() or None

    if normalized_category and normalized_category not in _ALLOWED_CATEGORIES:
        raise ValueError("Unsupported compliance category")
    if normalized_activity and normalized_activity not in _ALLOWED_ACTIVITIES:
        raise ValueError("Unsupported compliance activity")
    if normalized_channel and not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,59}", normalized_channel):
        raise ValueError("Channel must be a valid channel identifier")
    if normalized_category and normalized_activity and normalized_category not in REQUIRED_RULE_CATEGORIES[normalized_activity]:
        raise ValueError("Category is not required for the selected activity")

    matches: list[dict[str, Any]] = []
    for source in SOURCE_CATALOG:
        source_scope = str(source["jurisdiction_code"])
        if source_scope not in {requested_jurisdiction, GLOBAL}:
            continue
        if normalized_category and normalized_category not in source["categories"]:
            continue
        if normalized_activity and normalized_activity not in source["activities"]:
            continue
        source_channels = list(source["channels"])
        if normalized_channel and "any" not in source_channels and normalized_channel not in source_channels:
            continue
        public_source = {
            **source,
            "scope_match": "exact" if source_scope == requested_jurisdiction else "supplemental_global",
            "catalog_prepared_at": CATALOG_PREPARED_AT,
            "review_required": True,
            "legal_approval_granted": False,
        }
        matches.append(public_source)
    matches.sort(key=lambda item: (0 if item["scope_match"] == "exact" else 1, item["authority"].lower(), item["title"].lower()))
    return {
        "count": len(matches),
        "filters": {
            "jurisdiction": requested_jurisdiction,
            "category": normalized_category,
            "activity": normalized_activity,
            "channel": normalized_channel,
        },
        "catalog_prepared_at": CATALOG_PREPARED_AT,
        "data": matches,
        "notice": (
            "Starting references only. Open and review the live source, confirm its effective/current status and applicability, "
            "and record a substantive summary before adding evidence. A GLOBAL platform policy does not replace country-specific law. "
            "Catalog inclusion does not create evidence, approve an assessment or certify legal compliance."
        ),
    }
