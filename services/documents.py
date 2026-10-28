"""Text extraction and rule-based document analysis. Everything here is deterministic pattern matching:
findings are extracted passages plus templated explanations, NOT legal conclusions."""
import html, io, re, zipfile

MONTHS = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
DATE_RE = re.compile(rf"\b(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\.?,?\s+\d{{4}}|(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})\b", re.I)
AMT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?(?:\s?(?:lakhs?|crores?))?|[\d,]+(?:\.\d+)?\s?rupees", re.I)


def extract_text(name, data):
    """Returns (pages:list[str], error:str|None). OCR for scanned PDFs is NOT implemented."""
    ext = name.lower().rsplit(".", 1)[-1]
    try:
        if ext == "pdf":
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(data))
            if r.is_encrypted:
                return [], "The PDF is password-protected."
            pages = [(p.extract_text() or "") for p in r.pages]
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                info = z.getinfo("word/document.xml")
                if info.file_size > 50_000_000:
                    return [], "Document is too large to process safely."
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            paras = []
            for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
                paras.append("".join(html.unescape(t) for t in re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)))
            pages = ["\n\n".join(paras)]
    except Exception as e:
        return [], f"Could not read the file ({type(e).__name__})."
    if not any(p.strip() for p in pages):
        return pages, "No extractable text found. The file may be scanned (OCR is not enabled) or empty."
    return pages, None


def segments(pages):
    out = []
    for pn, page in enumerate(pages, 1):
        for para in re.split(r"\n\s*\n", page):
            para = re.sub(r"\s+", " ", para).strip()
            if len(para) < 25:
                continue
            if len(para) <= 700:
                out.append((pn, para)); continue
            cur = ""
            for s in re.split(r"(?<=[.;])\s+", para):
                if len(cur) + len(s) > 500 and cur:
                    out.append((pn, cur.strip())); cur = ""
                cur += " " + s
            if cur.strip():
                out.append((pn, cur.strip()))
    return out


CLAUSES = [
 ("Termination", r"\bterminat|\bnotice period|\bdetermine this (?:agreement|lease)", "Describes how or when the agreement can end.", "Medium"),
 ("Renewal", r"\brenew|\bextension of (?:the )?(?:term|agreement)|\bauto(?:matic(?:ally)?)?[- ]renew", "Describes whether and how the agreement continues after its initial term.", "Medium"),
 ("Payment", r"\bpayment|\bfees?\b|\brent\b|\binvoice|\bconsideration\b|\binterest\b|\bsecurity deposit", "Describes amounts, timing or conditions of payment.", "Medium"),
 ("Confidentiality", r"\bconfidential|\bnon-disclosure|\bproprietary information", "Restricts how information may be shared or used.", "Medium"),
 ("Dispute resolution", r"\barbitrat|\bjurisdiction|\bgoverning law|\bcourts? (?:at|of|in)\b|\bmediation|\bdispute", "Says where or how disagreements will be resolved and which law applies.", "Medium"),
 ("Penalty / liability", r"\bpenalt|\bliquidated damages|\bindemnif|\bliabilit|\bforfeit|\bdamages\b", "Describes financial consequences or responsibility if something goes wrong.", "High"),
 ("Obligation", r"\bshall\b|\bmust\b|\bagrees? to\b|\bundertakes? to\b|\bresponsible for\b", "States something a party is required to do.", "Low"),
]
CONCERNS = [
 ("sole discretion", r"sole (?:and absolute )?discretion|at any time without (?:notice|cause)|without assigning any reason", "Gives one party broad unilateral power. Worth confirming that this is intended.", "High"),
 ("automatic renewal", r"automatic(?:ally)? renew|auto-renew|deemed to be renewed", "The agreement may continue without a new decision. Check how and when you can opt out.", "Medium"),
 ("unlimited liability", r"unlimited liability|without (?:any )?limit|entire liability", "May expose a party to open-ended financial responsibility.", "High"),
 ("high interest or penalty", r"(?:\d{2,3}\s?%\s?(?:per|p\.)\s?(?:month|annum)|per month)[^.]{0,60}(?:interest|penalty|late)|(?:interest|penalty|late)[^.]{0,60}(?:\d{2,3}\s?%)", "A recurring percentage charge is stated. Confirm the rate and how it is calculated.", "Medium"),
 ("restraint after exit", r"non-compete|restrain(?:ed)? from|shall not (?:engage|work|solicit)", "Restricts activities after the relationship ends. Enforceability depends on facts and law and needs expert review.", "High"),
 ("one-sided forum", r"exclusive jurisdiction|sole arbitrator appointed by", "Fixes the forum or decision-maker. Check that the location and process are acceptable.", "Medium"),
 ("no notice period", r"immediate(?:ly)? terminat|terminat\w* (?:forthwith|with immediate effect)", "Termination may take effect without a notice period. Confirm this is understood.", "High"),
]
TYPE_HINTS = [("rental", r"landlord|tenant|lessee|lessor|\brent\b|licen[cs]e fee"), ("employment", r"employee|employer|employment|appointment"),
              ("service", r"service provider|scope of (?:work|services)|\bclient\b"), ("nda", r"non-disclosure|confidential information")]
CHECKLISTS = {
 "general": [("Parties named", r"between|party|parties|m/s"), ("Date of agreement", DATE_RE.pattern), ("Term or duration", r"\bterm\b|duration|period of"),
             ("Payment or consideration", r"payment|consideration|fees?|rent"), ("Termination clause", r"terminat"),
             ("Governing law / jurisdiction", r"governing law|jurisdiction"), ("Dispute resolution", r"arbitrat|mediation|dispute"),
             ("Signature block", r"signed|signature|witness|in witness whereof")],
 "rental": [("Landlord and tenant identified", r"landlord|lessor"), ("Property address", r"property|premises|situated at"), ("Monthly rent amount", r"rent"),
            ("Security deposit", r"deposit"), ("Lease term", r"term|period of|months"), ("Notice period", r"notice"),
            ("Maintenance responsibility", r"maintenance|repair"), ("Registration / stamp duty mention", r"regist|stamp"),
            ("Signature block", r"signed|signature|witness")],
 "employment": [("Employer and employee identified", r"employer|employee"), ("Role / designation", r"designation|position|role"), ("Salary / compensation", r"salary|remuneration|compensation|ctc"),
                ("Probation / notice period", r"probation|notice"), ("Confidentiality", r"confidential"), ("Termination terms", r"terminat"),
                ("Governing law / jurisdiction", r"governing law|jurisdiction"), ("Signature block", r"signed|signature|witness")],
 "service": [("Provider and client identified", r"service provider|client"), ("Scope of services", r"scope|services"), ("Fees and payment terms", r"fees?|payment|invoice"),
             ("Term", r"\bterm\b|duration"), ("Termination", r"terminat"), ("Confidentiality", r"confidential"), ("Liability limits", r"liabilit"),
             ("Dispute resolution", r"arbitrat|jurisdiction|dispute"), ("Signature block", r"signed|signature|witness")],
 "nda": [("Parties identified", r"between|party|parties"), ("Definition of confidential information", r"confidential information"), ("Permitted use", r"permitted|purpose"),
         ("Duration of obligation", r"period|years|duration"), ("Return / destruction of information", r"return|destr"), ("Dispute resolution", r"arbitrat|jurisdiction"),
         ("Signature block", r"signed|signature|witness")],
}


def detect_type(text):
    low = text.lower()
    scores = {t: len(re.findall(p, low)) for t, p in TYPE_HINTS}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "general"


def extract_entities(text):
    dates = list(dict.fromkeys(m.group(0) for m in DATE_RE.finditer(text)))
    amounts = list(dict.fromkeys(m.group(0).strip() for m in AMT_RE.finditer(text)))
    parties = []
    m = re.search(r"between\s+(.{3,120}?)\s+(?:and|&)\s+(.{3,120}?)(?:\s*[,(.]|\s+\(|\s+(?:on|dated|w\.e\.f)\b|\n|$)", text[:2500], re.I | re.S)
    if m:
        parties += [re.sub(r"\s+", " ", m.group(1)).strip(), re.sub(r"\s+", " ", m.group(2)).strip()]
    parties += re.findall(r"M/s\.?\s+[A-Z][\w&.\- ]{2,40}", text)
    roles = list(dict.fromkeys(re.findall(r'["“]the ([A-Z][A-Za-z ]{2,25})["”]', text)))
    return {"dates": dates[:30], "amounts": amounts[:30], "possible_parties": list(dict.fromkeys(parties))[:10], "defined_roles": roles[:10]}


def analyze(pages):
    text = "\n\n".join(pages)
    segs = segments(pages)
    findings, count = [], {}
    for pn, seg in segs:
        for cat, pat, expl, prio in CLAUSES:
            if re.search(pat, seg, re.I) and count.get(cat, 0) < 6:
                count[cat] = count.get(cat, 0) + 1
                findings.append({"kind": "clause", "category": cat, "passage": seg[:700], "explanation": expl, "page": pn,
                                 "reason": "Matched keywords for this clause type; classification is automatic and may be incomplete or wrong.", "priority": prio})
        for name, pat, reason, prio in CONCERNS:
            if re.search(pat, seg, re.I):
                findings.append({"kind": "clause", "category": "Potential concern", "passage": seg[:700], "explanation": f"Pattern noticed: {name}.",
                                 "page": pn, "reason": reason + " This is a prompt for human review, not a finding that the clause is unlawful.", "priority": prio})
    dtype = detect_type(text)
    checklist = []
    for item, pat in CHECKLISTS.get(dtype, CHECKLISTS["general"]):
        hit = next(((pn, s) for pn, s in segs if re.search(pat, s, re.I)), None)
        checklist.append({"kind": "checklist", "category": f"Checklist: {item}", "passage": hit[1][:500] if hit else "",
                          "page": hit[0] if hit else None, "priority": "Low" if hit else "Medium",
                          "explanation": "Related wording found." if hit else "No matching wording found. It may be absent, phrased differently, or in a part that could not be read.",
                          "reason": "Expected item for this document type." if hit else "Expected item not detected; please check the document manually."})
    ent = extract_entities(text)
    words = len(text.split())
    first = " ".join(re.split(r"(?<=[.])\s+", re.sub(r"\s+", " ", text).strip())[:2])[:500]
    summary = (f"Automatic extractive overview (not a legal summary). Probable type: {dtype}. {len(pages)} page(s), about {words} words. "
               f"Opening text: {first}")
    return {"doc_type": dtype, "summary": summary, "entities": ent, "findings": findings, "checklist": checklist}


SIMPLE_EXPLAIN = {
 "Termination": "This part says how the agreement can be ended and often how much notice is needed.",
 "Renewal": "This part says whether the agreement carries on after it ends and what you must do to stop that.",
 "Payment": "This part says how much has to be paid, when, and what happens if payment is late.",
 "Confidentiality": "This part says what information must be kept private and for how long.",
 "Dispute resolution": "This part says which law applies and where or how a disagreement would be decided.",
 "Penalty / liability": "This part says who bears the cost if something goes wrong, or what extra money may be charged.",
 "Obligation": "This sentence says what one side is required to do.",
 "Potential concern": "This wording may favour one side or have significant consequences, so read it carefully.",
}
