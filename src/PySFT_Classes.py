"""
    Module: PySFT_Classes
    ----------------------
    This module contains small class definitions used in the PySFT project.

"""

class CTimeout:
    def __init__(self, timeout: float):
        """
        Class to handle browser timeout settings.
        
        Args:
            timeout (float): Timeout duration in seconds.
        """
        self.timeout: float = timeout
    
    def seconds(self) -> float:
        return self.timeout
    def milliseconds(self) -> float:
        return self.timeout * 1e3