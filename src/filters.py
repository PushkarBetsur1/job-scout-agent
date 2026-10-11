"""Cheap rule-based eligibility/relevance checks that run before the (paid) LLM match."""
import re

from .collectors.base import Job

ALWAYS_EXCLUDE = re.compile(
    r"\b(intern|internship|co-?op|apprentice|postdoc|post-doc|technician|summer 20\d\d)\b", re.I
)
SENIOR = re.compile(
    r"\b(senior|sr|staff|principal|lead|manager|supervisor|director|head|vp|vice president|fellow|distinguished|iii|iv)\b", re.I
)
EARLY_TITLE = re.compile(
    r"new (college )?grad|\bncg\b|college grad|university grad|recent grad|\bgraduate\b|entry[- ]level|"
    r"early[- ]career|\bjunior\b|\bjr\b|\bassociate\b|\b(engineer|developer|designer)\s*(i|1)\b|class of 20\d\d",
    re.I,
)
EARLY_DESC = re.compile(
    r"new (college )?grad|recent(ly)? grad|university grad|college grad|entry[- ]level|early[- ]career|"
    r"\b0\s*(-|–|to)\s*[12]\+?\s*years|class of 20\d\d|graduating",
    re.I,
)
RELEVANT_TITLE = re.compile(
    r"hardware|embedded|firmware|electrical|electronic|computer eng|asic|fpga|\brtl\b|verilog|vlsi|\bsoc\b|"
    r"silicon|chip|semiconductor|analog|mixed[- ]signal|digital design|verification|validation|\bdft\b|"
    r"physical design|circuit|layout|\bcpu\b|\bgpu\b|architect|pcb|board|signal integrity|power|"
    r"systems? engineer|test engineer|product engineer|process engineer|device engineer|yield|packaging|"
    r"reliability|failure analysis|kernel|driver|\bbsp\b|bios|microcontroller|robotics|avionics|sensor|"
    r"\brf\b|wireless|photonic|low[- ]level",
    re.I,
)
ENGINEERING_TITLE = re.compile(r"engineer|developer|designer|scientist|programmer|\bsde\b", re.I)
CE_DEGREE = re.compile(r"computer engineering|electrical (?:and|&) computer engineering|\bECE\b|\bCompE\b", re.I)
STRONG_DESC_TERMS = re.compile(
    r"firmware|embedded|rtos|microcontroller|fpga|systemverilog|verilog|vhdl|\basic\b|\brtl\b|bare[- ]metal|"
    r"stm32|cortex-m|\bi2c\b|\bspi\b|\buart\b|device driver|trustzone|bootloader",
    re.I,
)
YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?years?(?:['’]s?)?\s+(?:of\s+)?(?:[\w/-]+\s+){0,4}?experience",
    re.I,
)


def evaluate(job: Job) -> tuple[bool, str, str]:
    """Returns (passed, reason, match_path) where match_path is 'role' or 'degree'."""
    title = job.title
    if ALWAYS_EXCLUDE.search(title):
        return False, "intern/co-op/technician title", ""

    early_title = bool(EARLY_TITLE.search(title))
    if SENIOR.search(title) and not early_title:
        return False, "senior-level title", ""

    title_relevant = bool(RELEVANT_TITLE.search(title)) or (
        job.semiconductor and bool(ENGINEERING_TITLE.search(title))
    )
    engineering_title = bool(ENGINEERING_TITLE.search(title))
    if title_relevant or engineering_title:
        job.ensure_details()
    desc = job.description

    path, reason = "role", "passed"
    if not title_relevant:
        strong_terms = {m.lower() for m in STRONG_DESC_TERMS.findall(desc)}
        if len(strong_terms) >= 2:
            pass
        elif engineering_title and CE_DEGREE.search(desc):
            path, reason = "degree", "accepts a Computer Engineering degree"
        else:
            return False, "not hardware/embedded/semiconductor and no Computer Engineering degree mention", ""

    years = [int(y) for y in YEARS.findall(desc)]
    early = early_title or job.early_hint or bool(EARLY_DESC.search(desc))
    if years and min(years) >= 3 and not early:
        return False, f"requires {min(years)}+ years of experience", ""

    return True, reason, path
