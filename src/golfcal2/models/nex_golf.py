from typing import Optional, Dict, Any

class NexGolfClub(GolfClub):
    """NexGolf club."""
    
    def __init__(
        self,
        name: str,
        url: str,
        address: str = "Unknown",
        timezone: str = "UTC",
        coordinates: Optional[Dict[str, float]] = None,
        variant: Optional[str] = None,
        product: Optional[str] = None,
        auth_service: Optional[AuthService] = None,
        club_details: Optional[Dict[str, Any]] = None,
        config: Optional[AppConfigProtocol] = None,
        clubAbbreviation: Optional[str] = None
    ) -> None:
        """Initialize NexGolf club."""
        # Extract clubAbbreviation from club_details if not provided
        if clubAbbreviation is None and club_details and 'clubAbbreviation' in club_details:
            clubAbbreviation = club_details['clubAbbreviation']
        
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
            clubAbbreviation=clubAbbreviation
        ) 