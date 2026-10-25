import re

ARTICLES = [
    {"id": "reset-password", "title": "Reset your password", "body": "Open Account > Sign in > Forgot password. Enter your account email and use the reset link within 15 minutes. Check spam if it has not arrived. Never share your password or a one-time code with support."},
    {"id": "payment-help", "title": "Payment failed or charged twice", "body": "Check order history before retrying a payment. A failed payment can leave a temporary bank hold, normally released within 5-7 business days. Ask a human support specialist to review two completed charges. Support never asks for card details or bank OTPs."},
    {"id": "delivery-help", "title": "Delivery and tracking", "body": "Tracking becomes available after dispatch. Standard delivery takes 3-5 business days. Tracking updates can take 24 hours. If a delivered package is missing, check with your reception or household and request a human review."},
    {"id": "refund-policy", "title": "Returns and refund policy", "body": "Delivered orders are eligible for human review within 30 days of delivery. Every refund needs approval. Processing, shipped, cancelled, refunded, and older orders are outside the automatic eligibility policy. This sandbox records internal decisions and never transfers money."},
    {"id": "app-help", "title": "Troubleshoot the store app", "body": "Update the app, check your internet connection, and restart it. On the website, try a private window to rule out extension issues. If the issue remains, share the error message and app version with a human support specialist. Never send credentials."},
]


def search_knowledge(query: str) -> list[dict]:
    patterns = [
        (r"password|login|log in|sign.?in|reset", "reset-password"),
        (r"payment|charged|charge|bank|card|checkout", "payment-help"),
        (r"track|deliver|ship|parcel|package", "delivery-help"),
        (r"refund|return|policy", "refund-policy"),
        (r"app|crash|error|website|working|technical|help", "app-help"),
    ]
    identifiers = [identifier for pattern, identifier in patterns if re.search(pattern, query, re.I)]
    return [next(article for article in ARTICLES if article["id"] == identifier).copy() for identifier in identifiers[:2]]
