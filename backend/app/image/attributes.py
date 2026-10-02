"""Image-prompt attribute detectors (rule-based, like Stage A's A02/A03). Each returns the matched evidence, so the
explanation UI can show why an attribute counts as present.

Attributes: subject_detail, style, composition, lighting, palette, mood, aspect_ratio, background, avoid.
They are lexicon/regex detectors: a phrase counts when it names the attribute ("watercolor", "close-up",
"golden hour", "pastel", "cozy", "16:9", "on a beach", "no text"). Limits: they do not understand that a subject
implies a mood or a setting, and "on a skateboard" counts as a background.
"""
import re

_I = re.IGNORECASE
ATTRIBUTES = ("subject_detail", "style", "composition", "lighting", "palette", "mood", "aspect_ratio", "background",
              "avoid")


def _rx(*patterns: str) -> list[re.Pattern]:
    return [re.compile(p, _I) for p in patterns]


PATTERNS: dict[str, list[re.Pattern]] = {
    "style": _rx(
        r"\b(?:photo(?:graph)?s?|photo-?realistic|hyper-?realistic|realistic|oil painting|painting|painted|"
        r"watercolou?r|acrylic|gouache|sketch(?:ed)?|pencil|charcoal|ink|drawing|drawn|illustration|illustrated|"
        r"cartoon|anime|manga|comic(?: book)?|3d(?: render)?|render(?:ed|ing)?|cgi|pixel art|vector|flat design|"
        r"low[- ]poly|digital art|concept art|line art|minimalist|surreal(?:ist)?|impressionis[tm]|cubis[tm]|"
        r"art deco|art nouveau|cyberpunk|steampunk|vaporwave|isometric|claymation|origami|stained glass|mosaic|"
        r"ukiyo-e|pop art|graffiti|cinematic|film still|polaroid|35mm|studio ghibli|pixar|disney|"
        r"draw|paint|sketch|logo|icon|poster|infographic)\b"),
    "composition": _rx(
        r"\b(?:close[- ]?ups?|extreme close[- ]up|macro|wide[- ](?:angle|shot)|full[- ]body|full[- ]length|headshot|"
        r"portrait shot|medium shot|long shot|establishing shot|bird'?s[- ]eye(?: view)?|aerial(?: view)?|"
        r"top[- ]down|overhead(?: view| shot)?|low[- ]angle|high[- ]angle|from (?:above|below|behind)|side view|"
        r"profile view|front view|rear view|centered|centred|rule of thirds|symmetric(?:al)?|panoramic|fish-?eye|"
        r"tilt[- ]shift|zoomed[- ](?:in|out)|in the foreground|framed by|composition|POV|first[- ]person|"
        r"portrait(?! (?:orientation|format|mode)))\b"),
    "lighting": _rx(
        r"\b(?:lighting|lit|backlit|golden hour|blue hour|sunset|sunrise|dusk|dawn|twilight|at night|night-?time|"
        r"moonlight|moonlit|candle-?lit|candlelight|neon|silhouetted?|sunlight|sunlit|sunny|overcast|studio light|"
        r"softbox|rim light|volumetric|god rays|glow(?:ing)?|shadows?|chiaroscuro|"
        r"(?:soft|hard|natural|warm|cold|cool|dim|bright|dramatic|ambient|morning|evening|window|day)[- ]?light)\b"),
    "palette": _rx(
        r"\b(?:pastels?|monochrom(?:e|atic)|black[- ]and[- ]white|b&w|gr[ae]yscale|sepia|vibrant|muted|"
        r"desaturated|saturated|neon colou?rs|earth(?:y)? tones?|warm tones?|cool tones?|colou?r palette|"
        r"colou?r scheme|colou?rful|duotone|two[- ]tone|shades of \w+|\w+ and \w+ colou?rs|"
        r"(?:red|blue|green|yellow|orange|purple|pink|gold(?:en)?|teal|cyan|magenta) tones?)\b"),
    "mood": _rx(
        r"\b(?:cozy|cosy|eerie|creepy|spooky|serene|peaceful|calm|dramatic|whimsical|playful|melanchol(?:y|ic)|"
        r"sad|joyful|happy|cheerful|mysterious|ominous|dreamy|dreamlike|romantic|epic|nostalgic|tense|gloomy|"
        r"uplifting|cute|adorable|scary|moody|majestic|lonely|chaotic|tranquil|haunting|futuristic|"
        r"atmosphere|atmospheric|mood|vibe|feel(?:ing)?)\b"),
    "aspect_ratio": _rx(
        r"\b\d{1,2}\s?:\s?\d{1,2}\b", r"--ar\b",
        r"\b(?:square|portrait (?:orientation|format|mode)|landscape (?:orientation|format|mode)|vertical|"
        r"horizontal|widescreen|wide ?format|banner|(?:desktop |phone |mobile )?wallpaper|instagram (?:post|story)|"
        r"story format|poster|thumbnail|cover photo|header)\b"),
    "background": _rx(
        r"\b(?:background|backdrop|setting|surrounded by|against an?|in front of|behind (?:a|an|the))\b",
        r"\b(?:in|on|at|under|inside|beside|near|by|over|across|through|among)\s+(?:a|an|the|my|some)?\s*"
        r"(?:\w+\s)?(?:forest|woods|jungle|beach|ocean|sea|lake|river|city|street|alley|room|kitchen|garden|park|"
        r"field|meadow|mountains?|hills?|desert|space|sky|clouds|snow|rain|cafe|café|office|studio|stage|castle|"
        r"village|countryside|island|cave|bedroom|library|market|road|bridge|rooftop|window|table|desk|grass|"
        r"water|night sky|galaxy|planet|moon|tree|valley|harbou?r|station|classroom|farm|temple|ruins)\b"),
    "avoid": _rx(r"\b(?:no|without|avoid(?:ing)?|exclude|excluding|don'?t (?:include|show|add)|do not (?:include|show|add)|"
                 r"never show|not include)\b\s+[\w' -]+"),
}

_WORD = re.compile(r"[a-z][a-z'-]+", _I)
STOPWORDS = set("""a an the of and or with in on at for to from by my me some any this that it its is are be as
into onto over under like very really just of""".split())
SUBJECT_DETAIL_MIN_WORDS = 3     # content words left beyond the head noun and attribute words


def find(attribute: str, text: str) -> list[str]:
    hits = []
    for p in PATTERNS[attribute]:
        hits += [m.group(0).strip() for m in p.finditer(text)]
    return list(dict.fromkeys(hits))


def content_words(text: str) -> list[str]:
    """Words describing the subject: not stopwords and not part of another attribute's evidence."""
    covered = " ".join(e for a in ATTRIBUTES if a not in ("subject_detail",) for e in find(a, text)).lower()
    return [w for w in _WORD.findall(text.lower()) if w not in STOPWORDS and w not in covered.split()]


def detect(text: str) -> dict[str, list[str]]:
    """{attribute: evidence}; an empty list means the attribute is missing. subject_detail is present when the
    subject has at least SUBJECT_DETAIL_MIN_WORDS + 1 content words (a head noun plus descriptive words)."""
    out = {a: find(a, text) for a in ATTRIBUTES if a != "subject_detail"}
    words = content_words(text)
    out["subject_detail"] = words if len(words) > SUBJECT_DETAIL_MIN_WORDS else []
    return {a: out[a] for a in ATTRIBUTES}


def coverage(text: str) -> dict[str, bool]:
    return {a: bool(v) for a, v in detect(text).items()}
