"""Check resume and cover-letter text for wording that reads as machine-written.

This is a style check, not a detector score: it flags stock AI phrasing,
filler and repetitive structure so the text can be rewritten in plain,
specific language. Facts are never changed here.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# Words and phrases that recruiters and AI detectors associate with generated text,
# each with a plainer alternative.
AI_TELLS = {
    "spearheaded": "led",
    "leveraged": "used",
    "leverage": "use",
    "utilized": "used",
    "utilize": "use",
    "orchestrated": "organised",
    "synergy": "(describe the actual teamwork)",
    "synergies": "(describe the actual teamwork)",
    "dynamic": "(remove)",
    "results-driven": "(remove; show a result instead)",
    "detail-oriented": "(remove; show it with a specific task)",
    "highly motivated": "(remove)",
    "passionate about": "interested in",
    "proven track record": "(give the actual record)",
    "seamlessly": "(remove)",
    "seamless": "smooth",
    "robust": "reliable",
    "cutting-edge": "(remove)",
    "delve": "look into",
    "meticulous": "careful",
    "meticulously": "carefully",
    "fostered": "built",
    "showcasing": "showing",
    "pivotal": "key",
    "furthermore": "also",
    "moreover": "also",
    "in today's fast-paced": "(remove)",
    "ever-evolving": "(remove)",
    "landscape": "(name the actual field)",
    "a testament to": "(remove)",
    "honed": "built",
    "adept at": "good at",
    "go-getter": "(remove)",
    "team player": "(show teamwork with an example)",
    "think outside the box": "(remove)",
    "best-in-class": "(remove)",
    "holistic": "overall",
    "streamlined": "simplified",
    "empowered": "helped",
    "excellent communication skills": "(show it: e.g. handled vendor follow-ups)",
}


@dataclass
class Finding:
    line: int
    kind: str
    text: str
    suggestion: str


def check(text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        low = line.lower()
        for phrase, better in AI_TELLS.items():
            if re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", low):
                findings.append(Finding(n, "stock phrase", phrase, better))
        if "—" in line:
            findings.append(Finding(n, "em dash", "—", "use a comma, colon or full stop"))
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if len(sentence.split()) > 30:
                findings.append(Finding(n, "long sentence", sentence[:60] + "...", "split into two plain sentences"))
    # Several bullets opening with the same verb reads as templated.
    starts = Counter(l.split()[0].lower() for l in lines if l.strip() and l[0].isalpha() and l.rstrip().endswith(".") and len(l.split()) > 4)
    for word, count in starts.items():
        if count >= 3:
            findings.append(Finding(0, "repeated opening", word, f"{count} lines start with '{word}'; vary the verbs"))
    return findings


def docx_text(path: str) -> str:
    import zipfile
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    out = []
    for p in paras:
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
        if t.strip():
            out.append(t.replace("&amp;", "&").replace("&apos;", "'").replace("&quot;", '"'))
    return "\n".join(out)
