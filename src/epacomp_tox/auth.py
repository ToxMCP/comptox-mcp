from typing import Dict, Optional

class EPACompToxAuth:
    """
    Authentication handler for EPA CompTox APIs.
    
    This class handles authentication with the EPA CompTox APIs.
    It can be replaced with a custom implementation by the user.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with API key.
        
        Args:
            api_key: EPA CompTox API key. If not provided, will attempt to use
                    environment variable EPA_COMPTOX_API_KEY.
        """
        self.api_key = api_key
        
    def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for EPA CompTox API requests.
        
        Returns:
            Dictionary of headers including the API key.
        """
        if not self.api_key:
            raise ValueError(
                "API key is required. Please provide it when initializing EPACompToxAuth."
            )
        
        return {"x-api-key": self.api_key}
    
    def get_api_key(self) -> str:
        """
        Get the API key.
        
        Returns:
            The API key.
        """
        if not self.api_key:
            raise ValueError(
                "API key is required. Please provide it when initializing EPACompToxAuth."
            )
        
        return self.api_key
