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
19. RELATIONSHIPS — COMPREHENSIVE GRAPH EXTRACTION
============================================================

The criminal-network graph depends on extracting ALL meaningful,
source-supported relationships.

Do NOT extract only the most important relationship.

For EVERY paragraph, sentence, event, transaction, communication record,
organizational statement, ownership statement, location statement,
vehicle statement, or evidence statement:

1. Identify all entities involved.
2. Identify every distinct relationship explicitly supported by the text.
3. Extract each relationship as a SEPARATE relationship object.
4. Preserve direction.
5. Preserve the actual grammatical participants.
6. Preserve useful temporal and transactional details in the relationship
   metadata where supported.
7. Preserve the exact source evidence supporting the relationship.

The objective is COMPLETE SOURCE-SUPPORTED RELATIONSHIP COVERAGE.

Do NOT stop after extracting one relationship from a sentence when the
sentence clearly establishes multiple independent relationships.


============================================================
19.1 CANONICAL RELATIONSHIP TYPES
============================================================

Use these canonical predicates when the source supports them:

OWNERSHIP / CONTROL
- OWNS
- CONTROLS
- BENEFICIAL_OWNER_OF
- REGISTERED_TO

IDENTITY / CONTACT
- HAS_PHONE
- HAS_ACCOUNT
- HAS_VEHICLE

ORGANIZATIONAL
- WORKS_FOR
- OPERATES

COMMUNICATION
- CALLED
- CONTACTED

FINANCIAL
- TRANSFERRED_FUNDS_TO
- RECEIVED_FUNDS_FROM
- PAID
- WITHDREW_FROM

OPERATIONAL
- POSSESSED
- USED
- DELIVERED_TO
- INTRODUCED_TO
- THREATENED
- ARRANGED_MEETING_WITH
- COLLUDED_WITH

SPATIAL / EVENT
- LOCATED_AT
- OCCURRED_AT
- PARTICIPATED_IN
- WITNESS_TO
- LOCATED_WITH

GENERAL
- ASSOCIATED_WITH


Do NOT invent predicate names.

Normalize equivalent wording to the canonical predicate.

Examples:

"owned" → OWNS
"controlled" → CONTROLS
"director of" → CONTROLS or the most precise supported organizational
relationship
"works at" → WORKS_FOR
"employee of" → WORKS_FOR
"called" → CALLED
"phoned" → CALLED
"contacted" → CONTACTED
"transferred Rs. 5 lakh to" → TRANSFERRED_FUNDS_TO
"paid Rs. 5 lakh to" → PAID
"received money from" → RECEIVED_FUNDS_FROM
"withdrew cash from" → WITHDREW_FROM
"used the vehicle" → USED
"registered in the name of" → REGISTERED_TO
"located at" → LOCATED_AT
"was present at" → LOCATED_AT only when the wording establishes
the person's presence at that location
"witnessed" → WITNESS_TO when the witness-to-event relationship
is explicitly stated


============================================================
19.2 EXTRACT RELATIONSHIPS ACROSS ALL NODE TYPES
============================================================

Relationships are NOT limited to PERSON → PERSON.

The subject and object may be:

PERSON
ORGANIZATION
PHONE
VEHICLE
ACCOUNT
LOCATION
INCIDENT
UNKNOWN
or another explicitly extracted supported entity type.

Examples:

PERSON → HAS_PHONE → PHONE

PERSON → HAS_ACCOUNT → ACCOUNT

PERSON → HAS_VEHICLE → VEHICLE

PERSON → WORKS_FOR → ORGANIZATION

PERSON → OWNS → ORGANIZATION

PERSON → CONTROLS → ORGANIZATION

ORGANIZATION → HAS_ACCOUNT → ACCOUNT

PERSON → USED → VEHICLE

VEHICLE → REGISTERED_TO → PERSON

VEHICLE → REGISTERED_TO → ORGANIZATION

PERSON → LOCATED_AT → LOCATION

VEHICLE → LOCATED_AT → LOCATION

INCIDENT → OCCURRED_AT → LOCATION

PERSON → PARTICIPATED_IN → INCIDENT

PERSON → WITNESS_TO → INCIDENT

PHONE → CALLED → PHONE

PERSON → CALLED → PERSON

ACCOUNT → TRANSFERRED_FUNDS_TO → ACCOUNT

ACCOUNT → TRANSFERRED_FUNDS_TO → ORGANIZATION

PERSON → PAID → PERSON

ACCOUNT → RECEIVED_FUNDS_FROM → PERSON


Only create these relationships when the source supports them.


============================================================
19.3 EXTRACT ALL RELATIONSHIPS FROM A SINGLE SENTENCE/EVENT
============================================================

A single sentence can establish multiple relationships.

Example:

"Vinod called Sandeep six times, met him at Sheikh Auto Works,
and handed him Rs. 5,00,000."

Extract separate relationships:

Vinod → CALLED → Sandeep

Vinod → ARRANGED_MEETING_WITH → Sandeep
OR another canonical meeting predicate only when actually supported

Vinod → PAID → Sandeep

Do NOT collapse all three facts into one relationship.

Another example:

"Sandeep used the black Scorpio to follow Vikram to Wadgaon Road."

Extract:

Sandeep → USED → black Scorpio

Sandeep → LOCATED_AT → Wadgaon Road

Sandeep → [explicitly stated action toward Vikram]

Do NOT omit the vehicle or location merely because the main action
is between two people.

Another example:

"Deshmukh Infra Ventures transferred Rs. 42 lakh from its ICICI account
to Trimurti Land Holdings LLP's Bank of Maharashtra account."

Extract the relevant entity/account relationships and financial
relationship supported by the text.

Preserve the amount and accounts in metadata where possible.


============================================================
19.4 STRUCTURED FACT RELATIONSHIPS
============================================================

When the source explicitly states a factual association, represent it
as a relationship even when the statement is not phrased as a conventional
relationship verb.

Examples:

"The registered mobile number of Ashok Deshmukh is +91..."
→

Ashok Deshmukh → HAS_PHONE → +91...

"The Scorpio is registered to Sheikh Auto Works."
→

Scorpio → REGISTERED_TO → Sheikh Auto Works

"Mahesh Oswal is proprietor of Oswal Bullion & Forex."
→

Mahesh Oswal → OWNS → Oswal Bullion & Forex

"Sunita Deshmukh is a nominee director of Trimurti Land Holdings LLP."
→

Sunita Deshmukh → CONTROLS → Trimurti Land Holdings LLP

Use the most semantically appropriate canonical relationship.

Do NOT create a relationship merely because two objects happen to appear
near each other.


============================================================
19.5 COMMUNICATION RELATIONSHIPS
============================================================

When communication details are present, extract them.

Examples:

"Phone A called Phone B 14 times."
→

Phone A → CALLED → Phone B

Metadata should preserve, where available:

{{
  "call_count": 14,
  "date": "..."
}}

"Vinod called Sandeep."
→

Vinod → CALLED → Sandeep

If both person and phone identities are explicitly provided, extract the
phone-level relationship when supported and preserve the person/phone
association separately.

Do NOT invent call counts, dates, times, or device identifiers.


============================================================
19.6 FINANCIAL RELATIONSHIPS
============================================================

Financial information should produce explicit transaction relationships
when the participants are identifiable.

Example:

"Account A transferred Rs. 25,00,000 to Account B."

→

Account A → TRANSFERRED_FUNDS_TO → Account B

Include metadata when available:

{{
  "amount": 2500000,
  "currency": "INR",
  "date": "...",
  "transaction_type": "TRANSFER"
}}

Example:

"Mahesh handed Rs. 5 lakh in cash to Vinod."

→

Mahesh → PAID → Vinod

metadata:

{{
  "amount": 500000,
  "currency": "INR"
}}

Do NOT invent transaction endpoints from contextual proximity.

If the amount is known but the sender or receiver is not known,
extract the monetary amount but do NOT fabricate a relationship.


============================================================
19.7 VEHICLE RELATIONSHIPS
============================================================

When a document states who owns, uses, operates, drives, or is associated
with a vehicle, extract the corresponding relationship.

Examples:

"Iqbal Sheikh provided the Scorpio."
→
Iqbal Sheikh → USED → Scorpio
only if the wording supports use/provision in the relevant semantic context.

"The Scorpio was registered in Sheikh Auto Works' name."
→
Scorpio → REGISTERED_TO → Sheikh Auto Works

"Sandeep was driving the Scorpio."
→
Sandeep → USED → Scorpio

"ANPR placed the Scorpio at Wadgaon Road."
→
Scorpio → LOCATED_AT → Wadgaon Road

Do not infer ownership from use.


============================================================
19.8 ORGANIZATION RELATIONSHIPS
============================================================

Extract explicit organizational relationships.

Examples:

"Ashok Deshmukh is Chairman of Deshmukh Infra Ventures."
→
Ashok Deshmukh → CONTROLS → Deshmukh Infra Ventures

"Sunita is nominee director of Trimurti Land Holdings LLP."
→
Sunita → CONTROLS → Trimurti Land Holdings LLP

"Kunal Mehta was an accountant at Deshmukh Infra Ventures."
→
Kunal Mehta → WORKS_FOR → Deshmukh Infra Ventures

Do not create organizational relationships from shared addresses,
shared documents, or simple co-occurrence.


============================================================
19.9 LOCATION RELATIONSHIPS
============================================================

Extract location connections whenever explicitly supported.

Examples:

"The meeting occurred at Chawla Associates."
→
Meeting/Incident → OCCURRED_AT → Chawla Associates

"Sandeep was seen at Wadgaon Road."
→
Sandeep → LOCATED_AT → Wadgaon Road

"The Scorpio was found near the crime scene."
→
Scorpio → LOCATED_AT → Crime Scene

Preserve time/date when explicitly present.

Do NOT convert a person's home address into an event/location relationship
unless the source context establishes that semantic fact.


============================================================
19.10 INCIDENT / EVENT PARTICIPATION
============================================================

When an incident/event explicitly identifies participants, extract
participant relationships.

Example:

"Sandeep, Prashant and Vinod participated in the planning meeting."

Extract separate relationships:

Sandeep → PARTICIPATED_IN → Incident/Event

Prashant → PARTICIPATED_IN → Incident/Event

Vinod → PARTICIPATED_IN → Incident/Event

If somebody is explicitly described as a witness:

Person → WITNESS_TO → Incident

If the event location is explicitly stated:

Incident/Event → OCCURRED_AT → Location


============================================================
19.11 INTRODUCTION RELATIONSHIPS
============================================================

For:

"Person A introduced Person B to Person C."

The actual grammatical introducer is Person A.

Use:

Person A → INTRODUCED_TO → Person B

unless the sentence semantics clearly establish another target.

Do not automatically use Person C as the target.

Preserve the full sentence as evidence.

Do not create unrelated additional relationships for Person C.


============================================================
19.12 UNKNOWN / UNIDENTIFIED ENDPOINTS
============================================================

If a relationship explicitly refers to an unknown or unidentified entity,
preserve the endpoint as UNKNOWN.

Example:

"Agent Blue delivered cash to Sameer."

If Agent Blue is explicitly unknown:

Agent Blue → DELIVERED_TO → Sameer

subject_type = UNKNOWN

Do NOT convert an unknown person into PERSON merely because they behave
like a person.

Do not invent a name or identity.


============================================================
19.13 RELATIONSHIP COMPLETENESS
============================================================

Before finishing extraction, perform a relationship-completeness pass.

Review the ENTIRE document again and identify every distinct
source-supported relationship.

Ask:

1. Did I capture every explicit person-person relationship?
2. Did I capture person-organization relationships?
3. Did I capture person-phone relationships?
4. Did I capture phone-phone communication relationships?
5. Did I capture person-vehicle relationships?
6. Did I capture vehicle-organization relationships?
7. Did I capture vehicle-location relationships?
8. Did I capture person-location relationships?
9. Did I capture organization-location relationships?
10. Did I capture organization-account relationships?
11. Did I capture account-account financial relationships?
12. Did I capture financial relationships between
    people, accounts, and organizations?
13. Did I capture incident participation?
14. Did I capture incident locations?
15. Did I capture event/location relationships?
16. Did I capture event/person relationships?
17. Did I capture every distinct relationship in
    multi-action sentences?
18. Did I preserve relationships across different
    sections of the document?
19. Did I preserve the MOST SPECIFIC predicate supported
    by the source?
20. Did I accidentally downgrade a specific relationship
    to ASSOCIATED_WITH?
21. Did I capture relationships whose endpoints are phones,
    vehicles, accounts, organizations, locations, or events?
22. Did I avoid creating unsupported relationships?

The objective is MAXIMUM SOURCE-SUPPORTED RELATIONSHIP COVERAGE,
not minimum relationship count.

============================================================
19.13.1 SPECIFIC RELATIONSHIP PRESERVATION
============================================================

Always prefer the most specific predicate explicitly supported
by the source.

Examples:

"Prashant followed Vikram."
→ FOLLOWED

"Prashant tracked Vikram."
→ FOLLOWED

"Prashant shadowed Vikram."
→ FOLLOWED

Do NOT reduce these to:

ASSOCIATED_WITH

when the source supports FOLLOWED.

Similarly:

"X owns Y"
→ OWNS

"X controls Y"
→ CONTROLS

"X works for Y"
→ WORKS_FOR

"X called Y"
→ CALLED

"X transferred funds to Y"
→ TRANSFERRED_FUNDS_TO

"X paid Y"
→ PAID

"X used vehicle Y"
→ USED

"X was located at Y"
→ LOCATED_AT

Do NOT replace a specific source-supported predicate with
ASSOCIATED_WITH merely because ASSOCIATED_WITH is broader.

ASSOCIATED_WITH should be used only when the source supports
an association but does not support a more specific predicate.

============================================================
19.13.2 PHONE RELATIONSHIP ENDPOINTS
============================================================

When the source explicitly refers to telephone numbers,
prefer phone endpoints over person endpoints when the
corresponding numbers are identifiable.

Example:

"Ashok's number called Vinod's number 14 times."

If Ashok's and Vinod's phone numbers are identifiable from
the document, extract:

AshokPhone --CALLED--> VinodPhone

Do NOT replace this with:

Ashok --CALLED--> Vinod

unless the source only supports the person-level relationship.

Likewise:

"Vinod called Sandeep's burner number 6 times."

If Sandeep's burner number is identifiable, extract:

VinodPhone --CALLED--> SandeepPhone

or the equivalent identifiable phone endpoint.

Preserve:

- call count
- date
- time/range
- relevant source context

when explicitly supported.

============================================================
19.13.3 EVENT AND LOCATION RELATIONSHIPS
============================================================

Preserve explicit relationships involving events or incidents.

Example:

"The planning meeting took place at Chawla Associates
in Dharampeth."

This may support:

PLANNING_MEETING --OCCURRED_AT--> Chawla Associates

and, when the source clearly establishes the location:

Chawla Associates --LOCATED_AT--> Dharampeth

Example:

"The murder occurred near the Panchsheel Green City
boundary wall."

Extract:

MURDER --OCCURRED_AT--> Panchsheel Green City boundary wall

Do not omit event/location relationships simply because
the event is represented in the incidents section.

Events and incidents are valid relationship endpoints.

============================================================
19.13.4 MULTI-ACTION SENTENCES
============================================================

Extract each distinct relationship independently.

Example:

"Prashant followed Vikram and called Sandeep 11 times."

This supports two relationships:

Prashant --FOLLOWED--> Vikram
Prashant --CALLED--> Sandeep

Do not collapse them into one relationship.

Likewise, if a sentence contains multiple transfers,
communications, ownership facts, locations, or actions,
extract each distinct source-supported relationship.

============================================================
19.13.5 RELATIONSHIP ENDPOINT PRIORITY
============================================================

Prefer the most precise identifiable endpoint.

For communication:

PHONE > PERSON

when a phone number is explicitly identified.

For financial transactions:

ACCOUNT > ORGANIZATION/PERSON

when the actual account is explicitly identified.

For vehicles:

VEHICLE > PERSON

when the vehicle itself is the object of the action.

For events:

EVENT/INCIDENT > PERSON

when the source explicitly relates a person to an event.

Do not invent an endpoint merely to obtain a more specific edge.

============================================================


============================================================
19.14 ANTI-HALLUCINATION RULE
============================================================

Do NOT manufacture relationships simply to make the graph dense.

Never create a relationship solely because:

- two entities appear in the same paragraph
- two entities appear in the same document
- two people are both accused
- two people are at the same location
- two people share an address
- two people work for the same organization
- two entities are mentioned together
- two names look similar
- one entity appears near another entity
- a relationship would be plausible

The source must provide an actual semantic or structured factual basis.

However, do NOT be overly conservative when the source DOES explicitly
contain the relationship.

The correct behavior is:

DO NOT INVENT.

DO NOT OMIT.


============================================================
19.15 RELATIONSHIP EVIDENCE
============================================================

Every relationship must contain concise source-grounded evidence.

Evidence must support the specific subject → predicate → object claim.

Good:

"14 calls were placed from Vinod's number to Sandeep's burner on 12/01."

Bad:

"Vinod and Sandeep were probably connected."

Do not fabricate quotations.

Preserve OCR uncertainty when necessary.


============================================================
19.16 RELATIONSHIP CONFIDENCE
============================================================

Every relationship MUST contain confidence from 0.0 to 1.0.

Confidence measures how strongly the source supports THIS relationship.

Use approximately:

0.95–1.00
Directly and explicitly stated.

0.90–0.94
Explicitly supported with minor normalization/interpretation.

0.80–0.89
Strongly supported but somewhat indirect or secondary.

0.65–0.79
Supported by contextual evidence, but not directly stated.

0.45–0.64
Ambiguous or weakly supported.

0.20–0.44
Weak implication.

Below 0.20
Highly speculative.

DO NOT extract highly speculative relationships.

Do not use confidence for:
- guilt
- criminal culpability
- entity-resolution confidence


============================================================
19.17 RELATIONSHIP METADATA
============================================================

When the source supports additional relationship-level facts, preserve
them in metadata.

Possible metadata:

{{
  "amount": ...,
  "currency": "...",
  "call_count": ...,
  "date": "...",
  "time": "...",
  "transaction_type": "...",
  "source_context": "..."
}}

Only include metadata supported by the source.

Do not invent metadata.


============================================================
19.18 FINAL RELATIONSHIP RULE
============================================================

The desired result is NOT:

"few highly important relationships."

The desired result is:

"EVERY MEANINGFUL, SOURCE-SUPPORTED RELATIONSHIP IN THE DOCUMENT."

A rich document should therefore produce a rich relationship graph.

Do not artificially cap the number of relationships.

Do not stop after extracting the first relationship involving an entity.

Do not collapse distinct relationships merely because the same two entities
are involved.

Preserve distinct relationships when they differ by:

- predicate
- date
- transaction
- event
- communication
- evidence

The final relationship list should represent the document's actual
network structure as completely as the evidence allows.

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
                    response_schema=DocumentExtraction,
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

            print("\n========== RAW GEMINI ENTITY CONFIDENCE ==========")

            for item in payload.get("organizations", []):
                print(
                    "ORGANIZATION:",
                    item.get("name"),
                    "confidence=",
                    item.get("confidence"),
                )

            for item in payload.get("locations", []):
                print(
                    "LOCATION:",
                    item.get("name") or item.get("address"),
                    "confidence=",
                    item.get("confidence"),
                )

            for item in payload.get("vehicles", []):
                print(
                    "VEHICLE:",
                    item.get("registration_number")
                    or item.get("description"),
                    "confidence=",
                    item.get("confidence"),
                )

            print("=================================================\n")

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

