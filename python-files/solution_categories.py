"""Shared solution-topic rules for cleaned data and visit reports."""

from __future__ import annotations

import re


HELPFUL_LINKS_LABEL = "Helpful Pages"

SOLUTION_TOPIC_RULES = [
    (
        HELPFUL_LINKS_LABEL,
        r"helpful\s+links?|help(?:ful)?\s+(?:pages?|sites?|sections?|cent(?:er|re)s?|articles?|resources?)|"
        r"24\s*/\s*7\s+(?:support|help)|quick support|support team|support resources|"
        r"training webinars?|capital iq pro academy|platform academy|what(?:['’]?s)?\s+new",
    ),
    (
        "Excel and Office Tools",
        r"\bexcel\b|\boffice\b|\bpowerpoint\b|\bppt\b|\bword\b|plug[\s-]?in|plugin|"
        r"templates?|formulas?|identifier converter",
    ),
    (
        "AI Tools",
        r"document intelligence|document viewer|chat.?iq|ask ai|ai summar|ai assisted|"
        r"ai-powered|key phrases?|transcript sentiment|chart explainer|"
        r"\bgen(?:erative)?\s*ai\b|\bai[- ]driven\b|\bai tools?\b",
    ),
    (
        "Company Profiles and Financial Data",
        r"corporate profiles?|company profiles?|financials?|estimates?|ownership|"
        r"company data|company information|securities summary|corporate tree|"
        r"fixed income|ratings\s*xpress|ratingsdirect|credit analytics|stock prices?",
    ),
    (
        "Screening",
        r"screen(?:er|ing)?|browse criteria|business involvement screens?|"
        r"language screening|idea generation screens?|search for the keyfield:\s*IQ_INDUSTRY_CLASSIFICATION|"
        r"^\s*\d+\s*>\s*add\s*$",
    ),
    (
        "Transactions and Deal Data",
        r"transactions?|deal profiles?|deal screening|m\s*&\s*a|mergers?|acquisitions?|"
        r"adviser fees?|spt[r_]|search for the keyfield:\s*SPTR_",
    ),
    (
        "Peer Comps and Valuation",
        r"peer comps?|peer analysis|comparables?|quick comps|multiples|valuation|"
        r"benchmark(?:ing)?",
    ),
    (
        "Dashboards, Watchlists and Alerts",
        r"dashboards?|watchlists?|alerts?|\blists?\b(?!\s+of\b)",
    ),
    (
        "News, Research and Market Data",
        r"\bnews\b|research|market data|economic data|macroeconomic|newsletters?|"
        r"filings?|country profile",
    ),
    (
        "Private Markets and Specialized Datasets",
        r"private markets?|private compan(?:y|ies)|private equity|venture capital|"
        r"\bPE firms?\b|preqin|private capital|investor data",
    ),
    (
        "APIs and Data Integration",
        r"\bapis?\b|data integration",
    ),
    (
        "Market Maps and Industry Data",
        r"market maps?|metals?|mining|commodit(?:y|ies)|industry data|sector data|"
        r"country risk scores?",
    ),
    (
        "Charting and Visualization",
        r"chart builder|charting tools?|charts?|visuali[sz]ation",
    ),
    (
        "Report Builder",
        r"report\s*builder",
    ),
    (
        "Platform Overview",
        r"\boverview\b.{0,120}\b(?:capital iq|ciq pro|the platform|platform)\b|"
        r"\b(?:capital iq pro|ciq pro|the platform)\b.{0,120}\boverview\b|"
        r"\bhigh[- ]level\b.{0,80}\b(?:capital iq|ciq(?:\s+pro)?|platform)\b",
    ),
    (
        "Platform Navigation and Settings",
        r"user profiles?|profile settings|account settings|user settings|\bsettings\b|display information|"
        r"settings and customization|platform navigation|search function|search bar|"
        r"platform overview|navigation within",
    ),
    (
        "Product Training and Learning",
        r"client training|product training|training for new users?|walkthrough|new users?|product overview",
    ),
    (
        "ESG",
        r"\besg\b",
    ),
]


def solution_topic_categories(text: str) -> list[str]:
    """Return every distinct canonical topic mentioned in a solution description."""
    return [
        label
        for label, pattern in SOLUTION_TOPIC_RULES
        if re.search(pattern, text, re.IGNORECASE)
    ]


def is_non_solution_entry(text: str) -> bool:
    """Identify CRM prompt answers and explanatory notes that are not solutions."""
    return bool(
        re.match(
            r"\s*what would they love to have\??\s*(?:n/?a|none|not applicable|nothing)\b|"
            r"\s*as client is onto\b.*\bthis would be the best product fit\b",
            text,
            re.IGNORECASE,
        )
    )
