"""Canonical consent wording and policy version for email-marketing evidence.

Changing the wording requires a new version identifier and review; callers cannot
substitute arbitrary client-supplied consent language.
"""
EMAIL_MARKETING_CONSENT_TEXT = (
    "I agree to receive this resource and related emails. I can unsubscribe at any time."
)
EMAIL_MARKETING_CONSENT_VERSION = "email-marketing-v1"
EMAIL_MARKETING_CONSENT_PURPOSE = "email_marketing"
