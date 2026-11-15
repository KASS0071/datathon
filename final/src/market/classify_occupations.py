"""Rule-based occupation groups from Indeed job titles (pipeline Branch B).

The Indeed data has no occupation field. Titles are lower-cased and matched
against ordered rules; the FIRST matching rule wins, so industry-specific
contexts (e.g. "medical assistant", "restaurant manager") are listed before
generic functions ("assistant", "manager"). Anything unmatched stays
"Other / unclassified". Nothing is guessed from the description text.

Groups are deliberately coarse (pipeline stop rule: "use a smaller set of
manually validated job categories rather than advanced NLP"). Accuracy is
checked against a hand-labelled sample in tests/fixtures/occupation_validation.csv.
"""
from __future__ import annotations

import re

import pandas as pd

UNCLASSIFIED = "Other / unclassified"

# Specific phrases that must beat an earlier, broader context word
# (found in the hand-validation sample).
OVERRIDES: list[tuple[str, str]] = [
    ("Software, data & IT", r"\b(?:software (?:dev\w*|engineer\w*)|sde)\b"),
    ("Sales", r"\b(?:sales rep\w*|sales representative)\b"),
    ("Personal care & service", r"\b(?:fitness|pilates|yoga|les mills)\b"),
    ("Retail & customer service", r"\b(?:clerk helper|general merchandise|assets? protection)\b"),
    ("Transportation, warehouse & logistics", r"\b(?:delivery driver|driver)\b"),
    ("Engineering & science (non-software)", r"\b(?:industrial hygien\w*|ehs engineer)\b"),
    ("Management (general)", r"\b(?:assistant manager|assistant branch manager|branch manager|assistant store manager|"
     r"assistant property manager|property manager)\b"),
    ("Business, finance & HR", r"\b(?:relationship manager|human resource|sales process)\b"),
    ("Retail & customer service", r"\b(?:brand advisor|brand representative|brand ambassador)\b"),
]

# (group, regex). Order matters: first match wins.
RULES: list[tuple[str, str]] = [
    ("Healthcare practitioners & support",
     r"\b(?:nurse|nursing|rn|lvn|lpn|cna|np|fnp|crna|physician|doctor|md|hospitalist|psychiatrist|pharmac\w*|"
     r"therapist|dental|dentist|hygienist|orthodont\w*|medical assistant|phlebotom\w*|radiolog\w*|sonograph\w*|"
     r"ultrasound|mri|ct tech\w*|x ray|surgical|surgeon|clinical|clinician|paramedic|emt|respiratory|"
     r"anesthesi\w*|optometr\w*|veterinar\w*|vet tech\w*|patient|medical|caregiver|home health|hospice|"
     r"physical therap\w*|occupational therap\w*|speech language|psychologist|dietitian|midwife|"
     r"chiropract\w*|audiolog\w*|lab assistant|laboratory technician|pa c|physician assistant|pediatrician|"
     r"technologist|scribe|pct|medicine|primary care|histolog\w*|pta|cota|dentistry|rda|rehabilitation|"
     r"health worker)\b"),
    ("Education & childcare",
     r"\b(?:teacher|teaching|tutor|instructor|preschool|pre k|educator|paraeducator|para educator|substitute|"
     r"professor|lecturer|childcare|child care|nanny|daycare|infant|toddler|school|faculty|coach|"
     r"camp counselor|admissions|child development|literacy|interventionist)\b"),
    ("Food service",
     r"\b(?:cook|chef|sous|server|dishwasher|barista|bartender|busser|host|hostess|crew|kitchen|food|"
     r"line cook|prep|restaurant|baker|bakery|cafe|catering|pizza|sushi|deli|dining|culinary|"
     r"boba|tea|coffee|bowl|burger|taco|grill|service team|take out|takeout|carside|dough|steward)\b"),
    ("Retail & customer service",
     r"\b(?:cashier|sales associate|retail|store|merchandis\w*|stocker|stock|customer service|customer support|"
     r"call center|team member|store clerk|sales clerk|shopper|beauty advisor|fragrance|cosmetic\w*|boutique|"
     r"grocery|pharmacy technician|optician|key holder|keyholder|shift lead\w*|shift supervisor|lot associate|"
     r"asset protection|product demonstrator|demonstrator|checkout|support associate|service advisor|"
     r"member services?|guest services?)\b"),
    ("Software, data & IT",
     r"\b(?:software|developer|programmer|swe|sde|devops|sre|site reliability|front ?end|back ?end|"
     r"full ?stack|machine learning|ml|ai|llm|deep learning|data engineer\w*|data scientist|data science|"
     r"data analyst|analytics|business intelligence|bi|cloud|platform engineer|infrastructure engineer|"
     r"it support|it specialist|it technician|it administrator|it analyst|it engineer|it manager|"
     r"information technology|it implementation|data platform|help ?desk|desktop support|systems administrator|sysadmin|network engineer|network administrator|"
     r"cyber ?security|security engineer|security analyst|ios|android|mobile engineer|web developer|"
     r"member of technical staff|mts|applied scientist|research scientist|research engineer|compiler|"
     r"kernel|gpu|database|dba|qa engineer|test automation|sdet|solutions architect|technical program manager|"
     r"product designer|ux|ui|statistician|quantitative|computer)\b"),
    ("Engineering & science (non-software)",
     r"\b(?:mechanical|electrical|civil|hardware|manufacturing engineer|process engineer|quality engineer|"
     r"test engineer|chemical|structural|design engineer|firmware|asic|rtl|fpga|dft|verification|"
     r"analog|silicon|semiconductor|layout|rf|optical|photonics|materials|biomedical|biolog\w*|chemist|"
     r"scientist|research associate|lab technician|engineer|engineering|architect)\b"),
    ("Care & social services",
     r"\b(?:social worker|case manager|counselor|behavior technician|behavioral|rbt|bcba|direct support|"
     r"mental health|aide|caseworker|community|youth|residential counselor|peer support|program specialist|"
     r"behavior support|victim)\b"),
    ("Skilled trades, maintenance & repair",
     r"\b(?:technician|tech|electrician|plumber|mechanic|maintenance|hvac|installer|carpenter|welder|"
     r"machinist|construction|painter|facilities|repair|apprentice|journeyman|foreman|laborer|landscap\w*|"
     r"gardener|roofer|solar|assembler|operator|fabricat\w*|production|utility worker|helper)\b"),
    ("Transportation, warehouse & logistics",
     r"\b(?:warehouse|driver|delivery|forklift|logistics|courier|package|material handler|shipping|receiving|"
     r"fulfillment|truck|cdl|chauffeur|valet|picker|packer|inventory|dispatch\w*|supply chain)\b"),
    ("Sales",
     r"\b(?:sales|account executive|business development|account manager|realtor|real estate agent|"
     r"insurance agent|loan officer|sdr|bdr)\b"),
    ("Business, finance & HR",
     r"\b(?:accountant|accounting|finance|financial|bookkeep\w*|payroll|auditor|audit|tax|human resources|"
     r"hr|recruiter|recruiting|talent|people|marketing|operations|project manager|product manager|"
     r"program manager|consultant|business analyst|analyst|compliance|legal|paralegal|attorney|lawyer|"
     r"underwriter|actuar\w*|controller|treasury|procurement|buyer|strategy|communications|"
     r"content|social media|brand|investment|banker|banking|estimator|accounts payable|accounts receivable|"
     r"client service associate|client associate|registered client)\b"),
    ("Office & administrative support",
     r"\b(?:administrative|admin|receptionist|office|coordinator|assistant|secretary|scheduler|front desk|"
     r"data entry|clerical|clerk|billing|records|concierge)\b"),
    ("Protective & building services",
     r"\b(?:janitor\w*|custodian|custodial|cleaner|cleaning|housekeep\w*|security|guard|porter|"
     r"environmental services|evs|groundskeeper|police|officer|deputy|investigator|firefighter|dispatcher)\b"),
    ("Personal care & service",
     r"\b(?:stylist|hair|barber|nail|esthetician|massage|groomer|pet|dog|fitness|trainer|spa|"
     r"lifeguard|attendant|recreation)\b"),
    ("Management (general)",
     r"\b(?:manager|management|supervisor|director|head of|vice president|vp|general manager)\b"),
]


def _pluralise(rx: str) -> str:
    """Allow a plural suffix on the final word of every alternative."""
    assert rx.startswith(r"\b(?:") and rx.endswith(r")\b"), rx[:30]
    return rx[:-3] + r")(?:s|es)?\b"


_COMPILED = [(g, re.compile(_pluralise(rx), re.I)) for g, rx in OVERRIDES + RULES]
GROUPS = [g for g, _ in RULES] + [UNCLASSIFIED]


def _normalise(title: str) -> str:
    t = str(title).lower()
    t = re.sub(r"[/|,()\-–—:+&]", " ", t)  # keep words, drop separators
    return re.sub(r"\s+", " ", t).strip()


def classify_title(title) -> str:
    if title is None or (isinstance(title, float) and pd.isna(title)):
        return UNCLASSIFIED
    t = _normalise(title)
    for group, rx in _COMPILED:
        if rx.search(t):
            return group
    return UNCLASSIFIED


def classify(titles: pd.Series) -> pd.Series:
    """Vectorised over unique titles (titles repeat heavily)."""
    uniq = pd.Series(titles.dropna().unique())
    mapping = dict(zip(uniq, uniq.map(classify_title)))
    return titles.map(mapping).fillna(UNCLASSIFIED)
