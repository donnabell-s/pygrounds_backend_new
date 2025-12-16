import re

def _has_any(patterns, text: str) -> bool:
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True
    return False



MASTER_KEYWORDS = [
    r"\btypevar\b", r"\bgeneric(s)?\b", r"\bcovariant\b", r"\bcontravariant\b",
    r"\bsingledispatch\b", r"\boverload\b", r"\bmetaclass\b",
    r"\bmappingproxytype\b", r"\bweakref\b", r"\bdescriptor(s)?\b",
    r"\bmethod resolution order\b", r"\bmro\b",
    r"\bprotocol\b", r"\biterator protocol\b",
    r"\bcoroutine(s)?\b", r"\bawaitable(s)?\b",
    r"\babstract base class(es)?\b", r"\babc\b",
    r"\bcontextmanager\b", r"\bdecorator(s)?\b",
]

ADVANCED_KEYWORDS = [
    r"\bbreak\b", r"\bcontinue\b", r"\bpass\b",
    r"\bternary\b", r"\bwalrus\b",
    r"\bpopitem\b", r"\bzfill\b", r"\bstrip\b",
    r"\bidentity\b",
    r"\bbitwise\b",
    r"\bindividual bits?\b",
    r"\bbit shift\b",
    r"\b(left|right)\s+shift\b",
    r"\breduce\b",
    r"\bfunctools\b",
    r"\baccumulate\b",
    r"\bconsume\b.*\breturn\b.*\bresult(s)?\b",
    r"\bbeyond simple iteration\b",
]
INTERMEDIATE_KEYWORDS = [
    r"\biterator(s)?\b", r"\biterable(s)?\b", r"\bgenerator(s)?\b",
    r"\bcomprehension(s)?\b",
    # type hints (catch common phrasing)
    r"\btype hint(s)?\b",
    r"\btype annotation(s)?\b",
    r"\bannotation(s)?\b",
    r"\btype information\b",
    r"\bfunction parameters?\b.*\breturn values?\b",
    r"\bparameter(s)?\b.*\breturn\b",
    # mutability
    r"\bhashable\b", r"\bmutable\b", r"\bimmutable\b",
    # slicing
    r"\bslice\b", r"\bslicing\b",
    r"\bstart\b.*\bstop\b.*\bstep\b",
    # dunder / special methods for string representation
    r"\bdunder\b",
    r"__str__|__repr__",
    r"\bspecial methods?\b.*\bstrings?\b",
    r"\bappear as strings?\b",
    r"\bstring representation\b",
    # closures
    r"\bclosure(s)?\b",
    r"\benclosing environment\b",
    r"\bfree variable(s)?\b",
    # design patterns (iterator pattern phrasing)
    r"\bdesign pattern\b.*\btravers\w+\b.*\bcollection",
    r"\bsequential access\b",
    r"\bsuppl(y|ies)\b.*\belements?\b.*\bsequential(ly)?\b",
    r"\bwithout exposing\b.*\bunderlying structure\b",
    # floor division nuance
    r"\bfloor division\b",
    r"\bnegative infinity\b",
    r"\btruncates?\b.*\bnegative infinity\b",
    r"\btype hint(s)?\b"
    r"\bannotation(s)?\b"
    r"\bparameter(s)?\b"
    r"\breturn value(s)?\b"
    r"\bslicing\b"
    r"\bstart\b.*\bstop\b.*\bstep\b"
]

# BEGINNER (syntax, basic ops, basic data concepts)
BEGINNER_KEYWORDS = [
    r"\bmodulo\b", r"\barithmetic\b",
    # conditionals (catch phrasing even if “if” not present)
    r"\bif\b", r"\belse\b",
    r"\bonly if\b",
    r"\bcondition is met\b",
    r"\btrue division\b"
    r"\bfloor division\b"
    r"\bset union\b"
    r"\bunion\b" 
    r"\bbitwise\b"
    r"\bfor loop\b",
    # common types
    r"\bstring\b", r"\blist\b", r"\binteger\b",
    r"\bboolean\b", r"\bvariable\b",
    # indentation / blocks
    r"\bindentation\b",
    r"\bcode blocks?\b",
    r"\bcurly braces?\b",
    # division operators phrasing
    r"\btrue division\b",
    r"\bwithout floor rounding\b",
    r"\boperator\b.*\bdivision\b",
    # conversion
    r"\bfloat\b",
    r"\bdecimal numbers?\b",
    r"\bconvert\b.*\btext\b.*\bdecimal\b",
    # ascii
    r"\bascii\b",
    r"\bspace\b.*\btilde\b",
    r"\bprintable\b.*\bcharacters?\b",
    # sets / union 
    r"\bset union\b",
    r"\bunion operation\b",
]

def refined_non_coding_rule_engine(text: str):
    """
    Returns: 'beginner' | 'intermediate' | 'advanced' | 'master' | None
    """
    t = (text or "").strip().lower()
    if not t:
        return None

    if "∪" in t:
        return "beginner"

    if _has_any(MASTER_KEYWORDS, t):
        return "master"

    if _has_any(ADVANCED_KEYWORDS, t):
        return "advanced"

    if _has_any(INTERMEDIATE_KEYWORDS, t):
        return "intermediate"

    if _has_any(BEGINNER_KEYWORDS, t):
        return "beginner"

    return None
