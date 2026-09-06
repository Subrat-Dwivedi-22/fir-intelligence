import json
import os

from google import genai
from google.genai import types

from app.services.llm.base import LLMService
from app.services.llm.models import (
    DocumentExtraction,
    IncidentAnalysis,
)

from app.services.llm.normalizer import (
    normalize_extraction_payload,
)


class GeminiLLMService(LLMService):
    """
    Gemini-backed LLM service.

    Responsibilities:
    - Semantic extraction from arbitrary law-enforcement documents.
    - Incident analysis for existing investigation functionality.

    Important architectural boundary:

        Gemini
            = semantic understanding

        Pydantic/application code
            = validation and normalization

        Repositories/services
            = persistence and entity resolution
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured"
            )

        self.model_id = model or os.getenv(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        )

        self.client = genai.Client(
            api_key=self.api_key
        )

    # ------------------------------------------------------------------
    # UNIVERSAL DOCUMENT EXTRACTION
    # ------------------------------------------------------------------

    def extract_document(
        self,
        text: str,
    ) -> DocumentExtraction:
        """
        Extract structured intelligence from arbitrary
        law-enforcement-related documents.

        The input document format is intentionally unknown.

        Gemini is responsible for semantic interpretation.
        Application code is responsible for validation and
        deterministic normalization.
        """

        if not text or not text.strip():
            return DocumentExtraction(
                document_type="UNKNOWN"
            )

        document_text = text.strip()

        prompt = f"""
You are the semantic extraction engine of a
law-enforcement document intelligence platform.

Your task is to read the supplied document and extract
STRUCTURED FACTS into the application's canonical schema.

The document format is UNKNOWN.

It may be an FIR, complaint, witness statement, seizure memo,
arrest document, investigation report, charge sheet, intelligence
report, financial investigation report, court document, notice,
letter, property document, vehicle document, or another
law-enforcement-related document.

You MUST NOT assume a particular document template.

Your job is to understand the meaning of the document and map
different ways of expressing the same concept into the canonical
schema.

============================================================
1. PRIMARY RULE
============================================================

EXTRACT WHAT THE DOCUMENT STATES.

Do not extract what you think is probably true.

Do not invent facts.

Do not fill missing information using general knowledge.

Do not infer facts simply because they appear likely.

When information is absent, return null or an empty list.

When information is ambiguous, preserve the ambiguity rather
than choosing an unsupported interpretation.

The document is the ONLY source of truth.

============================================================
2. FACTS VS INFERENCE
============================================================

The distinction between explicit facts and inference is critical.

ONLY extract a fact when the document provides evidence for it.

For example:

"The accused Rakesh met Mangesh at the office."

Supported:

- Rakesh is mentioned.
- Mangesh is mentioned.
- The document states that they met.
- The office is a location/context if explicitly identified.

NOT automatically supported:

- Rakesh and Mangesh are members of the same gang.
- Rakesh and Mangesh are associates.
- Rakesh owns the office.
- Mangesh participated in the crime.

Never convert contextual proximity into a relationship.

============================================================
3. DOCUMENT TYPE
============================================================

Classify the document using the information actually present.

Possible values include, but are not limited to:

- FIR
- COMPLAINT
- WITNESS_STATEMENT
- VICTIM_STATEMENT
- ACCUSED_STATEMENT
- ARREST_MEMO
- SEARCH_REPORT
- SEIZURE_MEMO
- INVESTIGATION_REPORT
- CASE_DIARY
- CHARGE_SHEET
- INTELLIGENCE_REPORT
- FINANCIAL_REPORT
- VEHICLE_DOCUMENT
- PROPERTY_DOCUMENT
- NOTICE
- LETTER
- COURT_DOCUMENT
- OTHER
- UNKNOWN

Do not force a classification when the document type is unclear.

============================================================
4. SEMANTIC LABEL NORMALIZATION
============================================================

Different documents frequently use different labels for the same
concept.

Interpret labels semantically rather than matching exact strings.

For example, all of these may represent a phone number:

- Phone
- Phone No
- Phone Number
- Mobile
- Mobile No
- Mobile Number
- Contact
- Contact No
- Contact Number
- Telephone
- Telephone No
- Cell
- Cell No
- Ph
- Ph No
- P. No.
- Mob
- Mob No

Map the value to:

phone_numbers

ONLY if the value is actually a telephone/mobile number.

Similarly, aliases may appear as:

- alias
- @
- aka
- a.k.a.
- also known as
- known as
- nickname
- nicknamed
- pseudonym

Map these to:

aliases

Addresses may appear as:

- Address
- Residing at
- Resident of
- R/o
- R/O
- Residence
- Lives at
- Permanent address
- Present address
- Native address

Map these to:

addresses

Parent/spouse information may appear as:

- S/o
- S/O
- D/o
- D/O
- W/o
- W/O
- Son of
- Daughter of
- Wife of
- Husband of
- Father
- Mother
- Guardian

Map explicit father/husband information to:

father_or_husband_name

Do not place unrelated relationship information into that field.

============================================================
5. PERSON IDENTIFICATION
============================================================

Extract every meaningful person explicitly identified in the
document.

Do not assume that every person is an accused.

A person can have one or more roles.

Possible roles include:

- COMPLAINANT
- INFORMANT
- ACCUSED
- SUSPECT
- VICTIM
- WITNESS
- OFFICER
- INVESTIGATING_OFFICER
- KEY_OPERATOR
- UNKNOWN_ACCOMPLICE
- DRIVER
- OWNER
- EMPLOYEE
- COURIER
- AGENT
- OTHER

Preserve multiple roles when explicitly supported.

Example:

"The complainant Rohit was threatened by accused Rakesh."

Rohit:

roles = ["COMPLAINANT"]

Rakesh:

roles = ["ACCUSED"]

Do not classify Rohit as an accused merely because he appears
in the incident.

Do not classify a witness as an accused unless the document
explicitly supports that role.

============================================================
6. UNKNOWN AND PARTIALLY IDENTIFIED PEOPLE
============================================================

Unknown identities are important intelligence objects.

Never invent a legal identity.

Examples:

- unknown male
- unknown female
- unknown person
- unidentified male
- unidentified person
- anonymous caller
- unknown accomplice
- unidentified foreign node

These must remain unknown or provisional.

Example:

"An unknown accomplice known as Agent Blue delivered the cash."

Correct:

name = "Agent Blue"

roles = ["UNKNOWN_ACCOMPLICE"]

aliases may include:

"Cash courier"

Do NOT invent a real name.

If the document provides only:

"Unknown male"

then preserve:

name = "Unknown male"

roles = ["UNKNOWN"]

============================================================
7. NAMES AND ALIASES
============================================================

Separate a person's actual name from aliases.

Example:

"Rakesh @ Raka"

Correct:

name = "Rakesh"

aliases = ["Raka"]

Example:

"Rakesh alias Raka"

Correct:

name = "Rakesh"

aliases = ["Raka"]

Do not create two separate people from an explicit alias.

Preserve meaningful spelling from the source.

Do not silently replace a person's name using outside knowledge.

============================================================
8. PHONE NUMBERS
============================================================

Extract explicitly stated telephone/mobile numbers.

Examples:

"P. No.: 9876543210"

→ phone_numbers = ["9876543210"]

"Mobile No: +91 98765 43210"

→ phone_numbers = ["+91 98765 43210"]

Do not invent a country code.

Do not mistake:

- FIR numbers
- case numbers
- account numbers
- vehicle registrations
- PIN codes
- postal codes
- dates

for phone numbers.

Preserve the original number unless a trivial formatting
normalization is obvious.



============================================================
8A. DOCUMENT-LEVEL CONTACT COMPLETENESS
============================================================

The top-level phone_numbers and email_addresses collections must
contain every explicitly mentioned phone number and email address
found anywhere in the document.

Person-level phone_numbers and email_addresses should additionally
associate those values with the relevant person when the document
supports that association.

Therefore, if:

"Sameer Khanna
Phone: +91-9822334455"

then:

document.phone_numbers =
["+91-9822334455"]

and:

person.phone_numbers =
["+91-9822334455"]

============================================================
9. EMAIL ADDRESSES
============================================================

Extract explicitly stated email addresses.

Do not construct or guess an email address.

If an email is partially obscured or ambiguous, preserve only
what can be reliably extracted.

============================================================
10. IDENTIFIERS
============================================================

Extract explicit identifiers such as:

- FIR numbers
- case numbers
- GD/DD entries
- complaint numbers
- document numbers
- reference numbers
- account numbers
- transaction identifiers
- registration numbers
- other clearly labeled identifiers

The identifier type must describe what the value represents.

Do not classify an identifier solely from its numeric appearance.

For example:

"FIR No: FIR-2026-3391"

must be treated as a FIR identifier, not a phone number.

============================================================
11. DATES AND TIMES
============================================================

Extract dates and times explicitly stated in the document.

Accept formats such as:

- 02/09/2026
- 02-09-2026
- 2 September 2026
- September 2, 2026
- 02.09.2026

Do not invent missing dates.

If the exact meaning of a date is unclear, preserve it in the
general dates collection and use incident-specific fields only
when supported.

Preserve ambiguous source representations rather than silently
changing their meaning.

============================================================
12. MONETARY AMOUNTS
============================================================

Extract all meaningful monetary amounts explicitly mentioned.

Examples:

- 18.5 Lakhs
- 45 Lakhs
- 2.5 Crores
- ₹18.5 lakh
- Rs. 18,50,000
- INR 1,850,000
- 5 million rupees

The numeric `amount` field must contain a numeric value only.

Examples:

"18.5 Lakhs"

→ amount = 1850000

"45 Lakhs"

→ amount = 4500000

"2.5 Crores"

→ amount = 25000000

Always preserve the original expression in:

original_text

If conversion cannot be performed reliably:

amount = null

but preserve:

original_text

Do not silently change currencies.



============================================================
12A. MONETARY AMOUNT COMPLETENESS
============================================================

Every explicit monetary amount in the document MUST be extracted
into monetary_amounts.

Do not omit an amount merely because it appears inside an evidence
description, incident narrative, recovery description, or bullet point.

For example:

"Hard cash amounting to 45 Lakhs was recovered."

MUST produce a monetary amount approximately equivalent to:

{{
    "amount": 4500000,
    "currency": "INR",
    "original_text": "45 Lakhs",
    "context": "Hard cash recovered",
    "evidence": "Hard cash amounting to 45 Lakhs was recovered."
}}

Common Indian monetary expressions include:

- lakh
- lakhs
- lac
- lacs
- crore
- crores
- thousand
- million
- billion
- Rs
- Rs.
- INR
- ₹

Do not omit monetary amounts simply because they are associated
with another extracted object.

============================================================
13. ORGANIZATIONS
============================================================

Extract organizations explicitly mentioned.

Examples include:

- police stations
- police departments
- banks
- companies
- firms
- shell companies
- government agencies
- government departments
- institutions
- financial institutions
- NGOs
- businesses

Example:

"Entity Owned: Apex Global Trading Ltd (Shell Company)"

Correct:

name = "Apex Global Trading Ltd"

organization_type = "shell company"

Do not assign an organization type that is not supported.

============================================================
14. LOCATIONS
============================================================

Extract explicitly stated locations.

Possible location types include:

- CITY
- DISTRICT
- STATE
- COUNTRY
- POLICE_STATION
- OFFICE
- BUILDING
- ROAD
- VILLAGE
- LANDMARK
- ADDRESS
- RESIDENCE
- OTHER

Do not infer precise geography from a partial name.

For example, if the document says:

"Diamond Plaza"

do not invent the city unless the document provides it.

============================================================
15. VEHICLES
============================================================

Extract explicitly mentioned vehicles.

Possible information:

- registration number
- vehicle type
- make/model
- color
- description

Example:

"Silver Sedan DL-08-CC-2109"

Possible extraction:

vehicle_type = "Sedan"

description = "Silver Sedan"

registration_number = "DL-08-CC-2109"

Do not mistake unrelated identifiers for registration numbers.

============================================================
16. EVIDENCE
============================================================

Extract explicitly mentioned evidence.

Evidence may include:

- cash
- weapons
- phones
- computers
- documents
- notebooks
- ledgers
- SIM cards
- bank records
- seals
- drugs
- vehicles
- property
- digital devices
- photographs
- recordings
- other physical or digital evidence

Preserve:

- description
- quantity
- value
- relevant context
- source evidence

Do not invent evidence merely because a crime normally involves it.



============================================================
16A. EVIDENCE COMPLETENESS
============================================================

Extract every explicitly mentioned significant physical or digital
piece of evidence into evidence_items.

Do not leave evidence_items empty when the document explicitly
contains recoveries, seized property, documents, devices, cash,
weapons, records, seals, notebooks, ledgers, phones, computers,
vehicles, or other evidence.

Example:

"RECOVERED EVIDENCE:
- Hard cash amounting to 45 Lakhs
- Stamp seals of 12 non-existent offshore shell firms
- Encrypted ledger notebook detailing hawala token codes"

MUST produce separate evidence_items for:

1. Hard cash
2. Stamp seals
3. Encrypted ledger notebook

Preserve quantities when explicitly stated.

For example:

{{
    "evidence_type": "CASH",
    "description": "Hard cash",
    "quantity": null,
    "value": "4500000",
    "evidence": "Hard cash amounting to 45 Lakhs"
}}

and:

{{
    "evidence_type": "SEALS",
    "description": "Stamp seals of non-existent offshore shell firms",
    "quantity": "12",
    "value": null,
    "evidence": "Stamp seals of 12 non-existent offshore shell firms"
}}

Do not invent evidence_type values when the document does not
support a specific classification. Use OTHER when necessary.

============================================================
17. INCIDENTS
============================================================

Extract significant events described in the document.

An incident may contain:

- title
- description
- dates
- times
- locations
- crime types
- key points
- modus operandi
- evidence

A document can contain multiple incidents.

Do not merge clearly separate incidents into one.

Do not create an incident merely because people or entities
are mentioned.

============================================================
18. CRIME TYPES AND OFFENCES
============================================================

Extract offences/crime types explicitly stated in the document.

Preserve useful legal identifiers where present.

For example:

"IPC Sec 420"

and:

"Prevention of Money Laundering Act (PMLA) Sec 3"

should be preserved as source-supported offence information.

Do not invent legal sections.

============================================================
19. RELATIONSHIPS
============================================================

Extract relationships ONLY when supported by explicit language.

Examples:

"Sameer transferred funds to Apex Global Trading Ltd."

→

subject = "Sameer"

subject_type = "PERSON"

predicate = "TRANSFERRED_FUNDS_TO"

object = "Apex Global Trading Ltd"

object_type = "ORGANIZATION"

Example:

"Agent Blue delivered cash to Sameer."

→

subject = "Agent Blue"

subject_type = "UNKNOWN"

predicate = "DELIVERED_TO"

object = "Sameer"

object_type = "PERSON"

Example:

"Rakesh threatened the complainant."

→

subject = "Rakesh"

subject_type = "PERSON"

predicate = "THREATENED"

object = "complainant"

object_type = "PERSON"

Use ONLY the following canonical predicates:

OWNS
CONTROLS
TRANSFERRED_FUNDS_TO
PAID
POSSESSED
USED
DELIVERED_TO
INTRODUCED_TO
THREATENED
ARRANGED_MEETING_WITH
COLLUDED_WITH
ASSOCIATED_WITH
LOCATED_AT

Do NOT invent, abbreviate, or modify predicate names.

For example:
"paid" → PAID
"paid money to" → PAID
"transferred funds to" → TRANSFERRED_FUNDS_TO
"introduced" → INTRODUCED_TO
"arranged a meeting with" → ARRANGED_MEETING_WITH

INTRODUCTION RELATIONSHIPS

For introduction statements, preserve the actual participants in the
introduction.

When the text has the form:

"Person A introduced Person B to Person C."

interpret the relationship as:

subject = Person A
predicate = INTRODUCED_TO
object = Person B

The evidence should preserve the full sentence.

Do not use Person C as the object merely because Person C appears after "to".

Example:

"Amit Sharma introduced Rajesh Kumar to Priya Mehta."

→

subject = "Amit Sharma"
subject_type = "PERSON"
predicate = "INTRODUCED_TO"
object = "Rajesh Kumar"
object_type = "PERSON"

If the sentence instead clearly states:

"Amit Sharma introduced Rajesh Kumar to Priya Mehta at the meeting."

the relationship remains:

Amit Sharma INTRODUCED_TO Rajesh Kumar

Do not create a separate relationship to Priya Mehta unless the document
explicitly establishes another relationship involving Priya Mehta.


RELATIONSHIP ARGUMENT ACCURACY

Extract relationships from the actual grammatical and semantic meaning of the
source text.

The subject and object must be the entities that actually participate in the
stated relationship.

Do not replace a person mentioned in the evidence with an organization merely
because the organization is mentioned nearby.

For example:

"Arjun introduced Neha to the company representative."

This does NOT establish:
Arjun INTRODUCED_TO Sunrise Property Ventures

unless the document explicitly states that Sunrise Property Ventures is the
entity/person being introduced to.

The correct interpretation may involve:
Arjun INTRODUCED_TO Neha
or another relationship involving the company representative, depending on
the exact schema and available entities.

Never use an organization as a relationship endpoint merely because an
organization appears in the surrounding sentence.

When the actual endpoint is described indirectly (for example, "the company
representative", "his associate", "the driver", "the manager"), preserve the
relationship only if the endpoint can be safely resolved from the document.
Otherwise do not invent an endpoint.

============================================================
ENTITY EXTRACTION CONFIDENCE
============================================================

For every extracted person, organization, location, and vehicle,
provide a confidence value from 0.0 to 1.0.

Confidence represents how strongly the document supports BOTH:

1. The existence/identity of the extracted entity.
2. The entity's documented relevance or involvement in the information
   being extracted.

Confidence is NOT a measure of criminal guilt, legal culpability,
or whether the entity is a suspect.

A witness, victim, complainant, police officer, family member, or
other non-suspect can still have high confidence when the document
clearly identifies them.

Use the following scale carefully:

0.95-1.00:
The entity is explicitly identified and directly involved in a
clearly documented event, action, transaction, or relationship.

Examples:
- "Rajesh Kumar paid ₹5,00,000 to ABC Ltd."
- "Priya Mehta was arrested at the location."
- "Vehicle DL01AB1234 was used in the incident."

0.90-0.94:
The entity is explicitly identified with strong supporting details,
but its involvement is somewhat less direct than the primary
participants.

Examples:
- A clearly identified person who arranged or facilitated an event.
- An organization explicitly identified as connected to a transaction.
- A clearly identified vehicle associated with the incident.

0.80-0.89:
The entity is clearly identified and relevant to the investigation,
but is primarily associated with or indirectly connected to the
main event.

Examples:
- An associate of an accused.
- An employee of an involved organization.
- A person who facilitated contact but did not participate directly.

0.65-0.79:
The entity is clearly mentioned and has a secondary or peripheral
connection.

Examples:
- A relative.
- A friend or acquaintance.
- A witness with limited involvement.
- An intermediary whose exact role is not central to the event.

0.45-0.64:
The entity is mentioned or partially identified, but the document
provides limited evidence about its relevance or connection.

0.20-0.44:
The entity is weakly implied, ambiguously identified, or supported
only by limited contextual evidence.

0.00-0.19:
The entity is highly speculative or insufficiently supported.
Do NOT create an entity merely because it seems plausible.

IMPORTANT:

Do not assign 1.0 merely because an entity's name appears explicitly.

Consider the entity's documented role, supporting details, and degree
of involvement when selecting the confidence value.

Do not automatically give every explicitly named entity the same
confidence.

Do not use confidence to indicate whether two mentions refer to the
same real-world entity. Entity resolution is handled separately by
the application.

Do not use confidence to indicate guilt, suspicion, or legal liability.

Confidence must reflect the evidence present in the source document,
not assumptions or outside knowledge.

============================================================
RELATIONSHIP EXTRACTION CONFIDENCE
============================================================

For every extracted relationship, provide a confidence value from
0.0 to 1.0.

Confidence represents how strongly the source document supports the
specific relationship between the subject and object.

Do NOT assign confidence based merely on the fact that both entities
appear in the same document.

Use the following scale:

0.95-1.00:
The relationship is directly and explicitly stated in the document.

Examples:
"Rajesh Kumar transferred Rs. 25,00,000 to ABC Infrastructure Pvt Ltd."
→ confidence should be approximately 0.95-1.00

"Amit Sharma threatened Rajesh Kumar."
→ confidence should be approximately 0.95-1.00

0.90-0.94:
The relationship is explicitly supported but requires minor
interpretation or normalization.

0.80-0.89:
The relationship is strongly supported by the document but is
indirect or involves a secondary role.

0.65-0.79:
The relationship is plausible and supported by contextual evidence,
but is not directly stated.

0.45-0.64:
The relationship is ambiguous or supported only by limited evidence.

0.20-0.44:
The relationship is weakly implied.

Below 0.20:
The relationship is highly speculative.
Do NOT extract the relationship merely because it seems plausible.

IMPORTANT:

Do not assign 1.0 to every explicitly stated relationship.

Use the full range appropriately.

Confidence measures the strength of evidence for THIS relationship,
not the confidence that the entities themselves are correctly resolved.

Do not use relationship confidence to indicate criminal guilt,
legal liability, or suspicion.

Do not infer a relationship solely from:
- co-occurrence
- shared addresses
- shared organizations
- being mentioned in the same incident
- being relatives
- being associates

unless the document explicitly supports the relationship.

Every relationship object MUST contain:
subject
subject_type
predicate
object
object_type
evidence
confidence

============================================================
19A. UNKNOWN RELATIONSHIP ENDPOINTS
============================================================

If a relationship endpoint refers to an explicitly unknown,
unidentified, anonymous, or provisional person, its object_type or
subject_type MUST be UNKNOWN.

Examples:

"Agent Blue delivered cash to Sameer Khanna."

If Agent Blue is explicitly described as an unknown accomplice:

subject_type = "UNKNOWN"

not:

subject_type = "PERSON"

Likewise:

"An unidentified foreign node received funds."

object_type = "UNKNOWN"

Do not convert an unknown identity into PERSON merely because the
entity behaves like a person.

A named alias or codename does not automatically establish a legal
identity.

============================================================
20. NEVER INFER RELATIONSHIPS
============================================================

Do NOT create a relationship merely because:

- two people are mentioned together
- two people are present at the same place
- two people work for the same organization
- two people are in the same paragraph
- two entities appear in the same document
- one person is mentioned near another
- two people share an address
- two people have similar names

Example:

"Rakesh and Mangesh were present at the scene."

Extract both persons.

Do NOT create:

Rakesh ASSOCIATED_WITH Mangesh

unless the document explicitly supports that relationship.

============================================================
21. RELATIONSHIP ENDPOINTS
============================================================

A relationship may reference an object that is not otherwise
fully described.

Example:

"Sameer colluded with an unidentified foreign node."

Valid relationship:

subject = "Sameer"
subject_type = "PERSON"

predicate = "COLLUDED_WITH"

object = "Unidentified Foreign Node"
object_type = "UNKNOWN"

Do not invent additional details about the foreign node.

============================================================
22. EVIDENCE FOR RELATIONSHIPS
============================================================

Every relationship must include evidence grounded in the source.

Good evidence:

"Sameer transferred funds to Apex Global Trading Ltd."

Bad evidence:

"Sameer is probably connected to Apex Global Trading Ltd."

The evidence must support the relationship directly.

============================================================
23. PROVENANCE
============================================================

For important extracted objects and events, provide concise
evidence from the source text.

Evidence should be:

- short
- factual
- directly supported
- close to the original wording

Do not fabricate quotations.

When the source wording is uncertain because of OCR, preserve
the uncertainty.

============================================================
24. OCR HANDLING
============================================================

The supplied text may contain OCR errors.

You may use surrounding context to understand an obvious OCR
mistake.

However:

- do not invent missing words
- do not fabricate names
- do not fabricate numbers
- do not silently rewrite uncertain information
- preserve source wording when uncertain

If an OCR value is ambiguous, prefer the safer interpretation
or leave the field null.

============================================================
25. CONFLICTING INFORMATION
============================================================

Documents may contain contradictions.

Example:

One section says:

"Rakesh's age is 32."

Another section says:

"Rakesh's age is 35."

Do NOT arbitrarily select one value.

Preserve the information that can be represented by the schema
and retain evidence showing the source statements.

Do not resolve contradictions using outside knowledge.

============================================================
26. DUPLICATES
============================================================

Do not create unnecessary duplicate objects when the document
clearly refers to the same person, organization, vehicle, or
location.

For example:

"Rakesh"

and:

"Rakesh @ Raka"

should normally represent the same person when context confirms
this.

However, if two references could represent different people,
do not merge them merely because the names are similar.

============================================================
27. FACTUAL CONSERVATISM
============================================================

When uncertain:

PREFER omission over invention.

PREFER null over guessing.

PREFER an unknown identity over an invented identity.

PREFER preserving source wording over silently correcting it.

PREFER multiple explicit facts over resolving a contradiction.

INCIDENT ASSOCIATION:

When a location, date, time, person, organization, vehicle, evidence item, or other fact
is explicitly described as part of an incident, associate it with that incident as well as
preserving it at the document level when appropriate.

Do not invent associations. Only associate a fact with an incident when the document
explicitly connects the fact to that incident or the association is unambiguous from the
document structure.

For example, if an incident section contains:
"Location: Diamond Plaza, 4th Floor, Office 402"
then the incident.locations field should contain:
"Diamond Plaza, 4th Floor, Office 402".

ROLE CONSERVATISM:
Do not assign a person role merely because the person is described as an
unknown accomplice, associate, courier, target, or otherwise involved.

Only assign a role when:
1. the document explicitly states the role, or
2. the role is an unambiguous synonym of an explicit description.

Do not infer legal classifications such as SUSPECT, ACCUSED, OFFENDER,
CULPRIT, or CONVICT unless the document explicitly uses that classification.

For example:
"Unknown Accomplice: Cash courier referred to as 'Agent Blue'"
should produce roles such as ["UNKNOWN_ACCOMPLICE", "COURIER"],
but should NOT automatically add "SUSPECT".

============================================================
28. FEW-SHOT EXAMPLES
============================================================

EXAMPLE A — PHONE LABEL

Source:

"P. No.: 9876543210"

Correct:

phone_numbers = ["9876543210"]

Reason:

"P. No." is being used as a phone-number label in this context.


EXAMPLE B — ALIAS

Source:

"Rakesh @ Raka, son of Mahesh"

Correct:

name = "Rakesh"
aliases = ["Raka"]
father_or_husband_name = "Mahesh"


EXAMPLE C — UNKNOWN PERSON

Source:

"An unknown male wearing a black jacket was seen leaving
the premises."

Correct:

name = "Unknown male"
roles = ["UNKNOWN"]

Do not invent a name.


EXAMPLE D — UNKNOWN ACCOMPLICE

Source:

"An unknown accomplice, a cash courier known as Agent Blue,
delivered the money."

Correct:

name = "Agent Blue"
roles = ["UNKNOWN_ACCOMPLICE"]
aliases = ["Cash courier"]

Do not invent a legal identity.


EXAMPLE E — MONEY

Source:

"Cash amounting to 18.5 Lakhs was recovered."

Correct:

amount = 1850000
original_text = "18.5 Lakhs"


EXAMPLE F — EXPLICIT RELATIONSHIP

Source:

"Sameer transferred funds to Apex Global Trading Ltd."

Correct:

subject = "Sameer"
subject_type = "PERSON"
predicate = "TRANSFERRED_FUNDS_TO"
object = "Apex Global Trading Ltd"
object_type = "ORGANIZATION"

The relationship is supported by the verb "transferred."


EXAMPLE G — NO INFERRED RELATIONSHIP

Source:

"Rakesh and Mangesh were present at the scene."

Correct:

Extract both people.

Do NOT create an ASSOCIATED_WITH relationship.

Co-occurrence is not sufficient evidence.


EXAMPLE H — EXPLICIT OWNERSHIP

Source:

"The vehicle DL-08-CC-2109 was owned by Rakesh."

Correct:

subject = "Rakesh"
subject_type = "PERSON"
predicate = "OWNS"
object = "DL-08-CC-2109"
object_type = "VEHICLE"


EXAMPLE I — CONFLICT

Source:

"Rakesh, aged 32, was arrested. The later report records his
age as 35."

Correct behavior:

Preserve both explicit age statements through the available
schema/evidence.

Do not decide that 32 or 35 is correct.

============================================================
29. OUTPUT CONTRACT
============================================================

Return ONLY valid JSON.

The JSON MUST conform to the DocumentExtraction Pydantic schema.

Do not return:

- Markdown
- ```json fences
- explanations
- commentary
- analysis
- additional top-level fields

Use:

[] for empty lists.

Use:

null for unavailable optional values.

All required fields must be present.

============================================================
30. FINAL QUALITY CHECK BEFORE OUTPUT
============================================================

Before returning JSON, internally verify:

1. Did I extract only information supported by the document?
2. Did I avoid inventing names or identities?
3. Did I preserve unknown people?
4. Did I separate names from aliases?
5. Did I map semantic labels rather than relying on exact labels?
6. Did I avoid treating every person as an accused?
7. Did I avoid unsupported relationships?
8. Did I preserve evidence for important facts?
9. Did I preserve original monetary expressions?
10. Did I avoid confusing identifiers with phone numbers?
11. Did I avoid inventing dates, locations, organizations, or
    vehicle details?
12. Did I preserve contradictions instead of silently resolving them?
13. Is the final result valid JSON matching the schema?

============================================================
DOCUMENT TO EXTRACT
============================================================

{document_text}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
        except Exception as exc:
            raise RuntimeError(
                "Gemini document extraction request failed"
            ) from exc

        raw = response.text

        if not raw or not raw.strip():
            raise ValueError(
                "Gemini returned an empty document extraction response"
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Gemini returned invalid JSON for document extraction"
            ) from exc

        try:
            normalized_payload = (
                normalize_extraction_payload(
                    payload
                )
            )

            return DocumentExtraction.model_validate(
                normalized_payload
            )
        except Exception as exc:
            raise ValueError(
                "Gemini document extraction did not match "
                "the DocumentExtraction schema"
            ) from exc

    # ------------------------------------------------------------------
    # EXISTING INCIDENT ANALYSIS
    # ------------------------------------------------------------------

    def analyze_incident(
        self,
        narrative: str,
        known_persons: list[str],
    ) -> IncidentAnalysis:
        """
        Analyze an incident narrative.

        This method is retained for compatibility with the existing
        investigation / analysis functionality.
        """

        if not narrative or not narrative.strip():
            return IncidentAnalysis()

        persons_text = ", ".join(
            person
            for person in known_persons
            if person and person.strip()
        )

        prompt = f"""
You are an analytical assistant for a criminal-intelligence
investigation system.

Analyze the incident narrative below.

Known persons:

{persons_text or "None"}

Incident narrative:

{narrative}

Return ONLY valid JSON matching the IncidentAnalysis schema.

Requirements:

1. Summarize the incident using only information supported by
   the narrative.

2. Extract important factual key points.

3. Identify modus operandi only when supported by the text.

4. Extract relationships only when explicitly supported.

5. Do not invent facts.

6. Do not assume guilt.

7. Do not infer relationships from simple co-occurrence.

8. Do not invent identities.

9. If information is unavailable, use null or an empty list.

10. Relationship evidence must be grounded in the narrative.

11. Return valid JSON only.

Do not return Markdown or explanatory text.
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
        except Exception as exc:
            raise RuntimeError(
                "Gemini incident analysis request failed"
            ) from exc

        raw = response.text

        if not raw or not raw.strip():
            raise ValueError(
                "Gemini returned an empty incident analysis response"
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Gemini returned invalid JSON for incident analysis"
            ) from exc

        try:
            return IncidentAnalysis.model_validate(
                payload
            )
        except Exception as exc:
            raise ValueError(
                "Gemini incident analysis did not match "
                "the IncidentAnalysis schema"
            ) from exc

