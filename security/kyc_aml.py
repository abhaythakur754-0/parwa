import re
from typing import Optional

class KYCCheck:
    """
    Stateless compliance validators for high-tier PARWA clients.
    Handles ID format validation and simulated sanctions list checks.
    """

    @staticmethod
    def validate_id_format(country_code: str, id_string: str) -> bool:
        """
        Validates the format of a government-issued ID based on country code.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code (e.g., 'US', 'UK').
            id_string: The ID string to validate.
            
        Returns:
            True if the format is valid, False otherwise.
            
        Raises:
            ValueError: If the country code is not supported.
        """
        country_code = country_code.upper()
        
        if country_code == "US":
            # US SSN format: XXX-XX-XXXX
            pattern = r"^\d{3}-\d{2}-\d{4}$"
            return bool(re.match(pattern, id_string))
        
        elif country_code == "UK":
            # UK National Insurance number format: 2 letters, 6 digits, 1 letter
            pattern = r"^[A-Z]{2}\d{6}[A-Z]$"
            return bool(re.match(pattern, id_string.upper()))
        
        else:
            raise ValueError(f"Country code '{country_code}' is not supported for ID validation.")

    @staticmethod
    def check_sanctions_list(entity_name: str) -> bool:
        """
        Simulated check against global sanctions lists.
        In a real scenario, this would call a third-party AML API (e.g., ComplyAdvantage).
        
        Args:
            entity_name: The name of the person or company to check.
            
        Returns:
            True if the entity is found on a sanctions list (BLOCKED), False otherwise (SAFE).
        """
        # Simulated blacklist for demonstration
        SANCTIONS_SIMULATION = ["KNOWN_BAD_ACTOR", "SANCTIONED_CORP", "TERROR_UNIT_7"]
        
        if any(bad_name in entity_name.upper() for bad_name in SANCTIONS_SIMULATION):
            return True
            
        return False
