import re

MASTER_KEYWORDS = [
    r"\brecurs(ion|ive|ively)\b",
    r"\bbacktracking\b",
    r"\b(dynamic programming|dp)\b",
    r"\bdecorator(s)?\b",
    r"\bcontext manager(s)?\b",
    r"\bwith\s+open\b",
    r"\b__enter__\b", r"\b__exit__\b",
    r"\basync\b", r"\bawait\b", r"\basyncio\b",
    r"\byield\b", r"\bgenerator(s)?\b",
    r"\bmetaclass\b",
    r"\bthread(s|ing)?\b|\bconcurren(t|cy)\b",
]

ADVANCED_KEYWORDS = [
    r"\bclass(es)?\b",
    r"\binheritance\b|\bpolymorphism\b|\bencapsulation\b|\babstraction\b",
    r"\bstaticmethod\b|\bclassmethod\b",
    r"\bexception handling\b|\btry\b.*\bexcept\b",
    r"\bfile i/o\b|\bread file\b|\bwrite file\b|\bopen\(\b",
    r"\bregex\b|\bregular expression\b",
    r"\bcomplexity\b|\bbig[\s-]?o\b",
    r"\bbinary\b",
    r"\bbitwise\b",
    r"\bbit mask\b|\bbitmask\b|\bmask\b",
    r"\bshift\b|\bleft shift\b|\bright shift\b",
    r"<<|>>",
    r"&|\||\^",
    r"\bcompound interest\b",
    r"\bloan\b",
    r"\bamortization\b|\bamortisation\b",
    r"\bmonthly payment\b",
    r"\bprincipal\b",
    r"\binterest rate\b",
]

BEGINNER_OVERRIDE_KEYWORDS = [
    r"\bcheck if number is even\b|\bcheck if number is odd\b",
    r"\beven\b|\bodd\b",
    r"\bmodulo\b|%",

    r"\bcreate an empty set\b|\bempty set\b",
    r"\badd(s|ing)? an element to a set\b|\badd to a set\b|\bset\.add\b",

    r"\bstartswith\b|\bendswith\b",
]

INTERMEDIATE_KEYWORDS = [
    r"\bfunction(s)?\b|\bdefine a function\b|\bdef\b",
    r"\bparameter(s)?\b|\bargument(s)?\b",
    r"\breturn\b",
    r"\bloop(s)?\b|\bfor loop\b|\bwhile loop\b",
    r"\bnested loop(s)?\b",
    r"\blist comprehension\b|\bdict comprehension\b|\bset comprehension\b",
    r"\blambda\b",
    r"\benumerate\b|\bzip\b",
    r"\bmap\b|\bfilter\b|\breduce\b",
    r"\bdictionary\b|\bhash map\b|\btuple\b",
    r"\bslice(s|ing)?\b",
    r"\bdocstring(s)?\b",
    r"\b__doc__\b",
    r"\binspect\.getdoc\b|\bgetdoc\b",
    r"\bpalindrome\b",
    r"\bidentity\b",
    r"\bis operator\b",
    r"\bsame object\b|\bidentical object(s)?\b",
    r"\bobject identity\b",
    r"\bchain assignment(s)?\b",
    r"\bassociativity\b",
    r"\bassignment operator(s)?\b|\baugmented assignment\b",
    r"\blogical operator(s)?\b",
    r"\bcondition(s)?\b|\bbased on condition(s)?\b",
    r"\b\+=\b|\b-=\b|\b\*=\b|\b/=\b|\b%=\b|\b//=\b|\b\*\*=\b",
]

BEGINNER_KEYWORDS = [
    r"\bvariable(s)?\b",
    r"\bprint\b",
    r"\binput\b",
    r"\barithmetic\b|\badd\b|\bsubtract\b|\bmultiply\b|\bdivide\b|\bmodulo\b",
    r"\bif\b|\belse\b|\belif\b",
    r"\bstring(s)?\b",
    r"\blist(s)?\b",

    r"\bstartswith\b",
    r"\bendswith\b",
]


def refined_coding_rule_engine(text: str):
    """
    Returns a difficulty override string if matched, else None.

    Priority:
    master -> advanced -> beginner_overrides -> intermediate -> beginner
    """
    t = (text or "").lower()

    for kw in MASTER_KEYWORDS:
        if re.search(kw, t):
            return "master"

    for kw in ADVANCED_KEYWORDS:
        if re.search(kw, t):
            return "advanced"

    for kw in BEGINNER_OVERRIDE_KEYWORDS:
        if re.search(kw, t):
            return "beginner"

    for kw in INTERMEDIATE_KEYWORDS:
        if re.search(kw, t):
            return "intermediate"

    for kw in BEGINNER_KEYWORDS:
        if re.search(kw, t):
            return "beginner"

    return None
