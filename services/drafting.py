"""Structured drafting. Missing facts become visible [PLACEHOLDER] markers; nothing is invented.
No statutory provisions are cited automatically: the advocate/user must add them."""
import re

REVIEW_NOTICE = ("DRAFT FOR HUMAN REVIEW - This draft is generated from the details you supplied. It is not legal advice and is not "
                 "guaranteed to be valid or suitable for court filing. Have a qualified advocate review it before use.")

# (key, label, kind, required)
T = {}


def _t(key, title, fields, body):
    T[key] = {"title": title, "fields": fields, "body": body}


_t("consumer_complaint", "Consumer complaint draft", [
    ("forum", "Forum / Commission", "text", True), ("complainant_name", "Complainant name", "text", True),
    ("complainant_address", "Complainant address", "area", True), ("opposite_party_name", "Opposite party name", "text", True),
    ("opposite_party_address", "Opposite party address", "area", True), ("product_or_service", "Product / service", "text", True),
    ("purchase_date", "Date of purchase / service", "text", True), ("amount_paid", "Amount paid", "text", False),
    ("grievance", "What went wrong", "area", True), ("steps_taken", "Steps already taken (e.g. complaints sent)", "area", False),
    ("relief_sought", "Relief sought", "area", True), ("place", "Place", "text", False), ("date", "Date", "text", False)],
 """# BEFORE THE {forum}

Complainant: {complainant_name}
Address: {complainant_address}

Opposite Party: {opposite_party_name}
Address: {opposite_party_address}

# COMPLAINT

1. The complainant obtained/availed: {product_or_service} on {purchase_date}, paying {amount_paid}.
2. Facts of the grievance: {grievance}
3. Steps already taken: {steps_taken}
4. Provisions relied upon: [PLACEHOLDER: to be added after advocate review]

# PRAYER
The complainant requests the following relief: {relief_sought}

Place: {place}
Date: {date}
Signature of Complainant: ____________________
""")
_t("legal_notice", "Legal notice draft", [
    ("sender_name", "Sender name", "text", True), ("sender_address", "Sender address", "area", True),
    ("recipient_name", "Recipient name", "text", True), ("recipient_address", "Recipient address", "area", True),
    ("subject", "Subject", "text", True), ("facts", "Facts", "area", True), ("demand", "What you demand", "area", True),
    ("deadline_days", "Days allowed to comply", "text", False), ("advocate_name", "Advocate (if any)", "text", False), ("date", "Date", "text", False)],
 """Date: {date}

From: {sender_name}, {sender_address}
To: {recipient_name}, {recipient_address}

# SUBJECT: {subject}

Sir/Madam,

Under instructions from and on behalf of {sender_name}, I/we state as follows:

1. Facts: {facts}
2. Demand: {demand}
3. You are called upon to comply within {deadline_days} days of receipt of this notice, failing which further action may be taken at your risk as to cost and consequences.
4. Legal provisions: [PLACEHOLDER: to be added after advocate review]

Advocate / Sender: {advocate_name}
Signature: ____________________
""")
_t("formal_response", "Response to a formal notice", [
    ("respondent_name", "Your name", "text", True), ("notice_sender", "Who sent the notice", "text", True),
    ("notice_date", "Date of the notice", "text", True), ("notice_ref", "Notice reference", "text", False),
    ("response_points", "Your response, point by point", "area", True), ("position", "Your position / what you propose", "area", True), ("date", "Date", "text", False)],
 """Date: {date}

To: {notice_sender}
Reference: {notice_ref}

# REPLY TO NOTICE DATED {notice_date}

I, {respondent_name}, acknowledge receipt of the above notice and respond as follows:

{response_points}

Position: {position}

All rights and contentions are reserved. Nothing in this reply is an admission.

Signature: ____________________
""")
_t("contract_outline", "Contract outline", [
    ("party_a", "First party", "text", True), ("party_b", "Second party", "text", True), ("purpose", "Purpose of the agreement", "area", True),
    ("term", "Term / duration", "text", False), ("consideration", "Consideration / price", "text", False),
    ("obligations", "Key obligations of each party", "area", False), ("jurisdiction", "Place of jurisdiction", "text", False)],
 """# CONTRACT OUTLINE (NOT A FINAL AGREEMENT)

1. Parties: {party_a} and {party_b}
2. Purpose: {purpose}
3. Term: {term}
4. Consideration: {consideration}
5. Key obligations: {obligations}
6. Termination and notice: [PLACEHOLDER: to be agreed]
7. Confidentiality: [PLACEHOLDER: to be agreed]
8. Dispute resolution and jurisdiction: {jurisdiction}
9. Signatures and witnesses: [PLACEHOLDER]
""")
_t("rental_agreement", "Rental agreement outline", [
    ("landlord", "Landlord name", "text", True), ("tenant", "Tenant name", "text", True), ("property_address", "Property address", "area", True),
    ("monthly_rent", "Monthly rent", "text", True), ("security_deposit", "Security deposit", "text", False), ("start_date", "Start date", "text", True),
    ("term_months", "Term (months)", "text", True), ("notice_days", "Notice period (days)", "text", False), ("date", "Date", "text", False)],
 """# RENTAL AGREEMENT OUTLINE (NOT A FINAL AGREEMENT)

Date: {date}
1. Landlord: {landlord}
2. Tenant: {tenant}
3. Property: {property_address}
4. Start date and term: {start_date}, for {term_months} months
5. Monthly rent: {monthly_rent}
6. Security deposit: {security_deposit}
7. Notice period for ending the tenancy: {notice_days} days
8. Maintenance, utilities, permitted use: [PLACEHOLDER: to be agreed]
9. Registration and stamp duty: [PLACEHOLDER: check requirements applicable in your State]
10. Signatures and witnesses: [PLACEHOLDER]
""")
_t("service_agreement", "Service agreement outline", [
    ("provider", "Service provider", "text", True), ("client", "Client", "text", True), ("services", "Services to be provided", "area", True),
    ("fee", "Fee", "text", True), ("payment_terms", "Payment terms", "text", False), ("term", "Term", "text", False), ("date", "Date", "text", False)],
 """# SERVICE AGREEMENT OUTLINE (NOT A FINAL AGREEMENT)

Date: {date}
1. Provider: {provider}
2. Client: {client}
3. Scope of services: {services}
4. Fee: {fee}; payment terms: {payment_terms}
5. Term: {term}
6. Confidentiality, intellectual property, liability limits: [PLACEHOLDER: to be agreed]
7. Termination: [PLACEHOLDER: to be agreed]
8. Dispute resolution: [PLACEHOLDER: to be agreed]
9. Signatures: [PLACEHOLDER]
""")
_t("affidavit", "Affidavit-format draft", [
    ("deponent_name", "Deponent name", "text", True), ("deponent_details", "Age / parentage / occupation", "text", False),
    ("address", "Address", "area", True), ("purpose", "Purpose of the affidavit", "text", True), ("statements", "Statements of fact (one per line)", "area", True),
    ("place", "Place", "text", False), ("date", "Date", "text", False)],
 """# AFFIDAVIT

I, {deponent_name}, {deponent_details}, resident of {address}, do hereby solemnly affirm and state as follows:

Purpose: {purpose}

{statements}

Verification: [PLACEHOLDER: verification wording to be added after advocate review]

Place: {place}
Date: {date}
Deponent: ____________________
(To be sworn/affirmed before an authorised officer. Not valid until properly attested.)
""")
_t("correspondence", "General legal correspondence", [
    ("sender", "Sender", "text", True), ("recipient", "Recipient", "text", True), ("subject", "Subject", "text", True),
    ("body_points", "Main points", "area", True), ("closing", "Closing request", "text", False), ("date", "Date", "text", False)],
 """Date: {date}
From: {sender}
To: {recipient}

# Subject: {subject}

Dear Sir/Madam,

{body_points}

{closing}

Yours faithfully,
{sender}
""")


class _Fill(dict):
    def __missing__(self, k):
        return f"[PLACEHOLDER: {k}]"


def validate(template_key, values):
    return [lbl for k, lbl, _, req in T[template_key]["fields"] if req and not (values.get(k) or "").strip()]


def render(template_key, values):
    spec = T[template_key]
    labels = {k: l for k, l, _, _ in spec["fields"]}
    fill = _Fill({k: ((values.get(k) or "").strip() or f"[PLACEHOLDER: {labels[k]}]") for k in labels})
    return REVIEW_NOTICE + "\n\n" + spec["body"].format_map(fill)


def placeholders(text):
    return re.findall(r"\[PLACEHOLDER[^\]]*\]", text)
