class PistonError(Exception):
    """The base exception type for all Piston related errors."""
    pass

class PistonNoOutput(PistonError):
    """Exception raised when no output was received from the API"""
    pass

class PistonInvalidStatus(PistonError):
    """Exception raised when the API request returns a non 200 status"""
    pass

class PistonInvalidContentType(PistonError):
    """Exception raised when the API request returns a non JSON content type"""
    pass
