from typing import Dict, Any, List
from app.models.domain import ChartData, User
from app.plugins.base_plugin import AstrologyPlugin

class NumerologyPlugin(AstrologyPlugin):
    """
    A standalone modular plugin that calculates Life Path and Destiny Numbers
    based on the User's Date of Birth without modifying core code.
    """
    
    def get_plugin_name(self) -> str:
        return "Numerology Core"
        
    def _reduce_number(self, num: int) -> int:
        """Reduces a number to a single digit conceptually (1-9) excluding master numbers (11, 22), 
           but keep it simple for example."""
        while num > 9 and num not in (11, 22):
            num = sum(int(digit) for digit in str(num))
        return num
        
    def process(self, chart_data: List[ChartData], user: User) -> Dict[str, Any]:
        """Calculates numerology vectors from user DOB."""
        if not user.dob:
            return {"error": "Date of Birth required for numerology"}
            
        try:
            # dob format expected: YYYY-MM-DD
            parts = user.dob.split("-")
            year = sum(int(d) for d in parts[0])
            month = sum(int(d) for d in parts[1])
            day = sum(int(d) for d in parts[2])
            
            life_path_val = self._reduce_number(year + month + day)
            day_number_val = self._reduce_number(day)
            
            return {
                "Life Path Number": life_path_val,
                "Day Number": day_number_val,
                "Summary": f"As a Life Path {life_path_val}, your path is defined by these core traits."
            }
            
        except Exception as e:
            return {"error": str(e)}
