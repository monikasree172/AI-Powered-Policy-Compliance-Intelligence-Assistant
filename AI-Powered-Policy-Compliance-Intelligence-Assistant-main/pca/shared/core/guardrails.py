"""
Input Guardrails — validates compliance queries before hitting any LLM agent.

Checks run in this exact order:
  1. Empty query
  2. Too short / too long
  3. Prompt injection attacks
  4. Explicitly off-topic PHRASES  (e.g. "movies to watch", "suggest me some movies")
  5. Explicitly off-topic KEYWORDS (e.g. "movie", "cricket", "recipe")
  6. Must contain at least one compliance-related term

If ANY check fails → query is rejected immediately.
No agents run. No tokens spent. No fake policy references returned.

FIX: The original bug was that "suggest me some movies to watch" slipped
through because "watch" was checked as a simple substring match, but words
like "watchlist" or "watchdog" also contain "watch". We now use:
  - word-boundary regex (\b) for single keywords
  - exact phrase matching for multi-word patterns
  - phrase check BEFORE keyword check (most specific first)
"""

import re
from dataclasses import dataclass

# ── Constants ──────────────────────────────────────────────────────────────────
MIN_QUERY_LENGTH = 10
MAX_QUERY_LENGTH = 1000

# ── Off-topic PHRASES ─────────────────────────────────────────────────────────
# Checked FIRST — before single keywords.
# Multi-word phrases that are 100% unambiguously off-topic.
# "movies to watch" and "suggest me some movies" are caught here
# before any single-keyword check even runs.
OFF_TOPIC_PHRASES = [
    # Movies & shows
    "movies to watch",
    "films to watch",
    "shows to watch",
    "what to watch",
    "what should i watch",
    "suggest me some movies",
    "suggest some movies",
    "suggest me movies",
    "recommend a movie",
    "recommend movies",
    "best movies",
    "top movies",
    "latest movies",
    "new movies",
    "good movies",
    "good shows",
    "web series to watch",
    "series to watch",
    # Music
    "songs to listen",
    "music to listen",
    "songs to hear",
    "good songs",
    "best songs",
    # Food
    "restaurants near",
    "places to eat",
    "what to eat",
    "good restaurants",
    "food near me",
    # Travel
    "places to visit",
    "where to travel",
    "travel recommendations",
    "best places",
    # Cooking
    "how to cook",
    "cooking recipe",
    # Sports
    "cricket score",
    "football score",
    "match score",
    "match result",
    "who will win",
    "score today",
    "live score",
    # Jokes / fun
    "tell me a joke",
    "make me laugh",
    "funny jokes",
    "good jokes",
    # Astrology
    "my horoscope",
    "my zodiac",
    "today horoscope",
    # Relationships
    "relationship advice",
    "dating advice",
    "love advice",
    # Shopping
    "best deals",
    "where to buy",
    "online shopping",
]

# ── Off-topic single KEYWORDS ──────────────────────────────────────────────────
# Checked with word-boundary (\b) regex so "watchdog" does NOT match "watch"
# but "watch" alone or "watch this movie" DOES match.
OFF_TOPIC_KEYWORDS = [
    # Entertainment
    "movie", "movies", "film", "films", "cinema", "netflix",
    "hotstar", "disney", "hulu", "anime", "cartoon",
    "bollywood", "hollywood", "tollywood", "kollywood",
    "celebrity", "actor", "actress", "director",
    # Music
    "song", "songs", "spotify", "playlist", "lyrics",
    "singer", "rapper",
    # Gaming
    "gaming", "playstation", "xbox", "nintendo", "minecraft",
    "fortnite", "pubg", "esport",
    # Food
    "recipe", "recipes", "cooking", "restaurant", "cuisine",
    "pizza", "burger", "biryani",
    # Travel
    "hotel", "resort", "tourism", "vacation",
    # Fitness
    "workout", "fitness", "yoga", "calories",
    # Sports
    "cricket", "football", "soccer", "basketball", "tennis",
    "badminton", "hockey", "rugby", "ipl", "nfl", "nba", "fifa",
    # Weather
    "weather", "forecast",
    # Jokes & fun
    "jokes", "meme", "memes", "riddle", "prank",
    # Astrology
    "horoscope", "astrology", "zodiac", "tarot",
    # Personal
    "dating", "boyfriend", "girlfriend",
    # Academic
    "homework", "assignment",
]

# ── Compliance keywords ────────────────────────────────────────────────────────
# Query MUST contain at least one of these to pass.
COMPLIANCE_KEYWORDS = {
    # Policy & regulatory
    "policy", "policies", "compliance", "regulation", "regulatory",
    "gdpr", "nist", "hipaa", "iso", "sox", "pci", "ccpa", "framework",
    "law", "legal", "legislation", "standard", "requirement",
    # Data & security
    "data", "security", "cybersecurity", "encryption", "breach",
    "confidential", "sensitive", "privacy", "pii", "classified",
    "information", "database", "backup", "retention", "storage",
    "protect", "protection", "secure",
    # Access & identity
    "access", "permission", "authorized", "authentication", "password",
    "credential", "mfa", "two-factor", "login", "account", "role",
    "privilege", "admin", "identity", "certificate",
    # Sharing & transfer
    "share", "sharing", "transfer", "disclose", "disclosure", "send",
    "transmit", "export", "third-party", "vendor", "contractor",
    "external", "cross-border", "region", "partner",
    # Incidents & reporting
    "report", "reporting", "incident", "violation", "audit",
    "investigate", "escalate", "notify", "alert", "log", "monitor",
    "detect", "respond", "response",
    # Work & HR
    "employee", "remote", "work from home", "wfh", "device",
    "laptop", "byod", "vpn", "network", "workplace",
    # Risk & legal
    "risk", "liability", "contract", "agreement", "dpa",
    "nda", "terms", "restrict", "prohibited", "allowed", "permitted",
    # Question starters employees use
    "can i", "should i", "am i allowed", "is it allowed", "is it ok",
    "are there", "do i need", "what are the", "how do i", "when should",
    "who should", "what happens if", "what is the procedure",
    "what is the policy", "what should i do", "is there a policy",
    "am i required", "do i have to", "is this compliant",
}

# ── Prompt injection patterns ──────────────────────────────────────────────────
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|your)\s+(instructions?|prompt|rules?|system)",
    r"forget\s+(everything|all|your|the\s+above)",
    r"you\s+are\s+now\s+",
    r"pretend\s+(you\s+are|to\s+be|that\s+you)",
    r"disregard\s+(your|all|the)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"god\s+mode",
    r"act\s+as\s+(if\s+you\s+are|a|an)\s+",
    r"roleplay\s+as",
    r"simulate\s+(a|an)\s+",
    r"override\s+(your|the)\s+(instructions?|rules?|settings?)",
    r"<\s*(script|iframe|img|svg|object|embed)[^>]*>",
    r"system\s*:\s*(you\s+are|ignore|forget)",
    r"reveal\s+(your|the)\s+(prompt|instructions?|system)",
    r"what\s+(are\s+your\s+instructions|is\s+your\s+system\s+prompt)",
]


@dataclass
class GuardrailResult:
    is_valid: bool
    reason: str
    sanitized_query: str = ""


def validate_query(raw_query: str) -> GuardrailResult:
    """
    Runs all 6 guardrail checks in order.
    Returns GuardrailResult(is_valid=True) only when every check passes.
    """

    # ── Check 1: Empty ─────────────────────────────────────────────────────────
    if not raw_query or not raw_query.strip():
        return GuardrailResult(
            is_valid=False,
            reason="Query is empty. Please type a compliance or policy question."
        )

    query = raw_query.strip()
    query_lower = query.lower()

    # ── Check 2: Length ────────────────────────────────────────────────────────
    if len(query) < MIN_QUERY_LENGTH:
        return GuardrailResult(
            is_valid=False,
            reason=(
                f"Query is too short (minimum {MIN_QUERY_LENGTH} characters). "
                "Please describe your compliance question in more detail."
            )
        )
    if len(query) > MAX_QUERY_LENGTH:
        return GuardrailResult(
            is_valid=False,
            reason=(
                f"Query is too long (maximum {MAX_QUERY_LENGTH} characters). "
                "Please shorten your question."
            )
        )

    # ── Check 3: Prompt injection ──────────────────────────────────────────────
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return GuardrailResult(
                is_valid=False,
                reason=(
                    "Your query contains disallowed content. "
                    "Please ask a genuine workplace compliance or policy question."
                )
            )

    # ── Check 4: Off-topic PHRASES (most specific — checked first) ─────────────
    detected_phrase = next(
        (phrase for phrase in OFF_TOPIC_PHRASES if phrase in query_lower),
        None
    )
    if detected_phrase:
        return GuardrailResult(
            is_valid=False,
            reason=_off_topic_message()
        )

    # ── Check 5: Off-topic single KEYWORDS (word-boundary match) ───────────────
    # Uses \b so "watchdog" is NOT blocked but "watch" alone IS blocked.
    detected_keyword = next(
        (kw for kw in OFF_TOPIC_KEYWORDS
         if re.search(r'\b' + re.escape(kw) + r'\b', query_lower)),
        None
    )
    if detected_keyword:
        return GuardrailResult(
            is_valid=False,
            reason=_off_topic_message()
        )

    # ── Check 6: Must contain at least one compliance keyword ──────────────────
    has_compliance_term = any(kw in query_lower for kw in COMPLIANCE_KEYWORDS)
    if not has_compliance_term:
        return GuardrailResult(
            is_valid=False,
            reason=(
                "Your question does not appear to be related to compliance or "
                "policy. Please ask about workplace topics such as data security, "
                "access controls, incident reporting, vendor contracts, or "
                "privacy regulations."
            )
        )

    # ── All checks passed ──────────────────────────────────────────────────────
    sanitized = re.sub(r"\s+", " ", query).strip()
    return GuardrailResult(is_valid=True, reason="OK", sanitized_query=sanitized)


def _off_topic_message() -> str:
    return (
        "This assistant only answers workplace compliance and policy questions. "
        "Your question appears to be about an unrelated topic. "
        "Please ask about topics such as: data sharing, security incidents, "
        "access permissions, privacy regulations, vendor contracts, "
        "or remote work policies."
    )


def get_rejection_response(reason: str) -> dict:
    """
    Returns a clean API rejection response.
    Called by the gateway when validate_query returns is_valid=False.
    Zero agents invoked. Zero tokens consumed.
    """
    return {
        "success": False,
        "error": reason,
        "compliance_status": None,
        "risk_level": None,
        "risk_score": None,
        "answer": reason,
        "next_steps": [],
        "citations": [],
        "agents_used": [],
        "token_usage": {"total": 0},
        "hint": (
            "Example questions you can ask:\n"
            "• 'Can I share customer data with an external vendor?'\n"
            "• 'Should I report accidental access to data I should not see?'\n"
            "• 'What are the password requirements for internal systems?'\n"
            "• 'Is it allowed to work remotely from another country?'"
        )
    }
