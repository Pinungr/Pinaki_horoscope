from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.models.domain import ChartData, User

class AstrologyPlugin(ABC):
    """
    Abstract base class for all Advanced Intelligence plugins.
    Conforms to Open/Closed SOLID principle.
    """
    
    @abstractmethod
    def get_plugin_name(self) -> str:
        """Returns the identifier name of the plugin."""
        pass
        
    @abstractmethod
    def process(self, chart_data: List[ChartData], user: User) -> Dict[str, Any]:
        """
        Executes the plugin's analytical logic.
        Returns a dictionary containing the output to be displayed or aggregated.
        """
        pass
