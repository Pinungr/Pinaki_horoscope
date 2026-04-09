import unittest
import logging
from app.utils.safe_execution import execute_safely, failure_registry, AppError
from app.services.horoscope_service import HoroscopeService

class MockDB:
    def __getattr__(self, name):
        return self

class TestFailureRegistry(unittest.TestCase):
    def test_failure_recording(self):
        failure_registry.clear()
        
        def failing_operation():
            raise ValueError("Something went wrong")
            
        res = execute_safely(
            failing_operation,
            operation_name="Test Op",
            user_message="Friendly error",
            fallback="fallback_value"
        )
        
        self.assertEqual(res, "fallback_value")
        failures = failure_registry.get_failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["operation"], "Test Op")
        self.assertEqual(failures[0]["message"], "Friendly error")

    def test_service_integration(self):
        # We don't need a real DB for this test if we mock the repos
        service = HoroscopeService(None)
        # Mocking user_repo.get_all to fail
        service.user_repo = type('Mock', (), {'get_all': lambda: 1/0})()
        
        failure_registry.clear()
        
        # This will fail internally but be caught by execute_safely in get_all_users_dicts 
        # (Wait, get_all_users_dicts doesn't use execute_safely yet? Let's check.)
        # Actually, get_all_users_dicts in horoscope_service.py:395 doesn't use execute_safely.
        # But _evaluate_chart_predictions does.
        
        service.rule_repo = type('Mock', (), {'get_all': lambda: 1/0})()
        res = service._evaluate_chart_predictions([])
        
        self.assertEqual(res, {})
        failures = service.get_service_failures()
        self.assertTrue(any(f["operation"] == "Rule repository fetch" for f in failures))

if __name__ == "__main__":
    unittest.main()
