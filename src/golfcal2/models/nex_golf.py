from typing import Any


class NexGolfClub(GolfClub):
    """NexGolf club."""
    
    club_abbreviation: str | None = None

    def __init__(
        self,
        name: str,
        url: str,
        address: str = "Unknown",
        timezone: str = "UTC",
        coordinates: dict[str, float] | None = None,
        variant: str | None = None,
        product: str | None = None,
        auth_service: AuthService | None = None,
        club_details: dict[str, Any] | None = None,
        config: AppConfigProtocol | None = None,
        club_abbreviation: str | None = None
    ) -> None:
        """Initialize NexGolf club."""
        # Extract club_abbreviation from club_details if not provided
        if club_abbreviation is None and club_details and 'club_abbreviation' in club_details:
            club_abbreviation = club_details['club_abbreviation']
        
        super().__init__(
            name=name,
            url=url,
            address=address,
            timezone=timezone,
            coordinates=coordinates,
            variant=variant,
            product=product,
            auth_service=auth_service,
            club_details=club_details,
            config=config,
            club_abbreviation=club_abbreviation
        ) 