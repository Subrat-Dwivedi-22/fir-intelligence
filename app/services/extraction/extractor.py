from app.services.extraction.models import (
    ExtractedFIR,
    ExtractedPerson,
)
from app.services.extraction.rules import (
    extract_fir_number,
    extract_phone_numbers,
)


class FIRExtractor:

    def extract(
        self,
        text: str,
    ) -> ExtractedFIR:

        fir = ExtractedFIR()

        # Deterministic extraction
        fir.fir_number = extract_fir_number(
            text
        )

        # Phones
        phones = extract_phone_numbers(
            text
        )

        if phones:
            fir.persons.append(
                ExtractedPerson(
                    name="UNKNOWN",
                    phone_numbers=phones,
                )
            )

        return fir