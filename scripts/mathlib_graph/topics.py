"""Topic names, colors, and layout bands for Mathlib modules."""

TOPIC_STYLE = {
    "Logic": ("#2563eb", 18),
    "Data": ("#334155", 30),
    "Order": ("#0f766e", 42),
    "Algebra": ("#ca8a04", 56),
    "RingTheory": ("#f97316", 68),
    "FieldTheory": ("#eab308", 80),
    "GroupTheory": ("#dc2626", 92),
    "LinearAlgebra": ("#7c3aed", 104),
    "Topology": ("#0891b2", 116),
    "Analysis": ("#16a34a", 128),
    "MeasureTheory": ("#059669", 140),
    "Probability": ("#0284c7", 152),
    "CategoryTheory": ("#9333ea", 164),
    "Geometry": ("#db2777", 176),
    "AlgebraicGeometry": ("#be123c", 188),
    "NumberTheory": ("#a16207", 200),
    "Combinatorics": ("#b91c1c", 212),
    "Tactic": ("#4f46e5", 224),
    "AlgebraicTopology": ("#06b6d4", 224.8),
    "Computability": ("#1d4ed8", 225.6),
    "Condensed": ("#0d9488", 226.4),
    "Dynamics": ("#ea580c", 228.8),
    "InformationTheory": ("#0369a1", 229.6),
    "Lean": ("#155e75", 230.4),
    "ModelTheory": ("#c026d3", 231.2),
    "RepresentationTheory": ("#e11d48", 232.0),
    "SetTheory": ("#65a30d", 232.8),
    "Other": ("#64748b", 236),
}

OTHER_TOPICS = {"Init", "Control", "Deprecated", "Testing", "Util"}


def topic_from_module(module: str, fallback: str | None = None) -> str:
    if fallback and fallback in OTHER_TOPICS:
        return "Other"
    if fallback and fallback in TOPIC_STYLE:
        return fallback
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "Mathlib":
        candidate = parts[1]
        if len(parts) >= 3 and f"{parts[1]}{parts[2]}" in TOPIC_STYLE:
            return f"{parts[1]}{parts[2]}"
        if candidate in OTHER_TOPICS:
            return "Other"
        if candidate in TOPIC_STYLE:
            return candidate
    if fallback:
        return fallback
    return "Other"


def color_for_topic(topic: str) -> str:
    return TOPIC_STYLE.get(topic, TOPIC_STYLE["Other"])[0]


def band_for_topic(topic: str) -> float:
    return float(TOPIC_STYLE.get(topic, TOPIC_STYLE["Other"])[1])


def namespace_lane(module: str) -> str:
    parts = module.split(".")
    if len(parts) >= 3 and parts[0] == "Mathlib":
        return ".".join(parts[1:3])
    if len(parts) >= 2 and parts[0] == "Mathlib":
        return parts[1]
    return module


def sub_namespace(module: str) -> str:
    parts = module.split(".")
    if len(parts) >= 4 and parts[0] == "Mathlib":
        return ".".join(parts[3:])
    return ""
