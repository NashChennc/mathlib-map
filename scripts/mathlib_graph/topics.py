"""Topic names, colors, and layout bands for Mathlib modules."""

TOPIC_STYLE = {
    "Logic": ("#1d4ed8", 10),
    "SetTheory": ("#2563eb", 20),
    "ModelTheory": ("#7c3aed", 30),
    "Computability": ("#0f766e", 40),
    "CategoryTheory": ("#9333ea", 55),
    "Condensed": ("#14b8a6", 65),
    "Data": ("#475569", 80),
    "Order": ("#0d9488", 90),
    "Combinatorics": ("#dc2626", 100),
    "InformationTheory": ("#0284c7", 110),
    "Algebra": ("#ca8a04", 130),
    "GroupTheory": ("#b91c1c", 140),
    "RingTheory": ("#f97316", 150),
    "FieldTheory": ("#eab308", 160),
    "LinearAlgebra": ("#6d28d9", 170),
    "RepresentationTheory": ("#e11d48", 180),
    "NumberTheory": ("#a16207", 190),
    "Geometry": ("#db2777", 210),
    "AlgebraicGeometry": ("#be123c", 220),
    "Topology": ("#0891b2", 230),
    "AlgebraicTopology": ("#06b6d4", 240),
    "Analysis": ("#16a34a", 260),
    "MeasureTheory": ("#059669", 270),
    "Probability": ("#0ea5e9", 280),
    "Dynamics": ("#ea580c", 290),
    "Lean": ("#155e75", 315),
    "Tactic": ("#4f46e5", 325),
    "Other": ("#64748b", 340),
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
