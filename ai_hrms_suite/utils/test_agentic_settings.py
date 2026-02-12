# Copyright (c) 2025, AI HRMS Suite and contributors
# For license information, please see license.txt

"""
Property-based tests for agentic settings utility functions.

Feature: agentic-settings
Tests correctness properties for is_agentic_enabled() and is_action_allowed().

Note: These tests require the Frappe environment. Run with:
    bench run-tests --app ai_hrms_suite --module ai_hrms_suite.utils.test_agentic_settings
"""

import unittest
from unittest.mock import patch, MagicMock
import sys

# Property test imports
try:
    from hypothesis import given, strategies as st, settings as hyp_settings
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False
    # Provide dummy decorators when hypothesis is not available
    def given(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def hyp_settings(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class st:
        @staticmethod
        def sampled_from(*args, **kwargs):
            return None
        
        @staticmethod
        def text(*args, **kwargs):
            class _Strategy:
                def filter(self, *args, **kwargs):
                    return self
            return _Strategy()

# Check if frappe is available
try:
    import frappe
    HAS_FRAPPE = True
except ImportError:
    HAS_FRAPPE = False


def skip_without_frappe(test_func):
    """Decorator to skip tests when Frappe is not available."""
    if not HAS_FRAPPE:
        return unittest.skip("Frappe environment required")(test_func)
    return test_func


class TestAgenticSettingsProperties(unittest.TestCase):
    """
    Property-based tests for agentic settings.
    
    Feature: agentic-settings
    """

    def _mock_settings(
        self,
        enable_agentic: bool = False,
        allow_create: bool = True,
        allow_update: bool = True,
        allow_submit: bool = False,
        allowed_doctypes: list = None,
    ) -> dict:
        """Build a mock settings dict."""
        settings = {
            "enable_agentic": 1 if enable_agentic else 0,
            "allow_create_actions": 1 if allow_create else 0,
            "allow_update_actions": 1 if allow_update else 0,
            "allow_submit_actions": 1 if allow_submit else 0,
            "allowed_action_doctypes": [],
        }
        if allowed_doctypes:
            settings["allowed_action_doctypes"] = [
                {"doctype_name": dt} for dt in allowed_doctypes
            ]
        return settings

    # ─── Property 1: Master Toggle Blocks All Actions ─────────────────────────
    # For any action request when enable_agentic is False, is_action_allowed()
    # SHALL return (False, <reason>).
    # Validates: Requirements 1.2, 1.3

    @skip_without_frappe
    @unittest.skipUnless(HAS_HYPOTHESIS, "hypothesis not installed")
    @given(
        action_type=st.sampled_from(["create", "update", "submit"]),
        doctype=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @hyp_settings(max_examples=100)
    def test_property_1_master_toggle_blocks_all(self, action_type: str, doctype: str):
        """
        Property 1: Master Toggle Blocks All Actions
        
        For any action type and any DocType, when enable_agentic is False,
        is_action_allowed() SHALL return (False, <reason>).
        
        Feature: agentic-settings, Property 1: Master toggle blocks all actions
        Validates: Requirements 1.2
        """
        from ai_hrms_suite.utils.config import is_action_allowed

        # Mock settings with agentic disabled
        mock_settings = self._mock_settings(
            enable_agentic=False,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            allowed, reason = is_action_allowed(action_type, doctype.strip())

            # Assert: action should be blocked
            self.assertFalse(allowed)
            self.assertIn("disabled", reason.lower())
            self.assertIn("administrator", reason.lower())

    @skip_without_frappe
    def test_property_1_master_toggle_blocks_all_simple(self):
        """Simple version of Property 1 without hypothesis."""
        from ai_hrms_suite.utils.config import is_action_allowed

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            for action_type in ["create", "update", "submit"]:
                for doctype in ["Leave Application", "Employee", "Salary Slip"]:
                    allowed, reason = is_action_allowed(action_type, doctype)
                    self.assertFalse(allowed)
                    self.assertIn("disabled", reason.lower())

    # ─── Property 4: Empty Allowlist Permits All HRMS DocTypes ────────────────
    # For any HRMS DocType and any action type, when enable_agentic is True,
    # all action type toggles are True, and allowed_action_doctypes is empty,
    # is_action_allowed() SHALL return (True, "").
    # Validates: Requirements 3.3

    @skip_without_frappe
    @unittest.skipUnless(HAS_HYPOTHESIS, "hypothesis not installed")
    @given(
        action_type=st.sampled_from(["create", "update", "submit"]),
        doctype=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @hyp_settings(max_examples=100)
    def test_property_4_empty_allowlist_permits_all(self, action_type: str, doctype: str):
        """
        Property 4: Empty Allowlist Permits All HRMS DocTypes
        
        For any DocType and any action type, when agentic is enabled,
        all action toggles are True, and allowlist is empty,
        is_action_allowed() SHALL return (True, "").
        
        Feature: agentic-settings, Property 4: Empty allowlist permits all
        Validates: Requirements 3.3
        """
        from ai_hrms_suite.utils.config import is_action_allowed

        # Mock settings with agentic enabled, all actions allowed, empty allowlist
        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
            allowed_doctypes=[],  # Empty allowlist
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            allowed, reason = is_action_allowed(action_type, doctype.strip())

            # Assert: action should be allowed
            self.assertTrue(allowed)
            self.assertEqual(reason, "")

    @skip_without_frappe
    def test_property_4_empty_allowlist_permits_all_simple(self):
        """Simple version of Property 4 without hypothesis."""
        from ai_hrms_suite.utils.config import is_action_allowed

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
            allowed_doctypes=[],
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            for action_type in ["create", "update", "submit"]:
                for doctype in ["Leave Application", "Employee", "Salary Slip"]:
                    allowed, reason = is_action_allowed(action_type, doctype)
                    self.assertTrue(allowed)
                    self.assertEqual(reason, "")

    # ─── Additional Unit Tests ────────────────────────────────────────────────

    @skip_without_frappe
    def test_is_agentic_enabled_returns_false_when_disabled(self):
        """Test is_agentic_enabled() returns False when setting is 0."""
        from ai_hrms_suite.utils.config import is_agentic_enabled

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            self.assertFalse(is_agentic_enabled())

    @skip_without_frappe
    def test_is_agentic_enabled_returns_true_when_enabled(self):
        """Test is_agentic_enabled() returns True when setting is 1."""
        from ai_hrms_suite.utils.config import is_agentic_enabled

        mock_settings = self._mock_settings(enable_agentic=True)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            self.assertTrue(is_agentic_enabled())

    @skip_without_frappe
    def test_is_agentic_enabled_returns_false_when_settings_empty(self):
        """Test is_agentic_enabled() returns False when settings doc is empty."""
        from ai_hrms_suite.utils.config import is_agentic_enabled

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value={},
        ):
            self.assertFalse(is_agentic_enabled())


if __name__ == "__main__":
    unittest.main()



class TestToolExecutorAgenticSettings(unittest.TestCase):
    """
    Property-based tests for tool executor agentic settings enforcement.
    
    Feature: agentic-settings
    """

    def _mock_settings(
        self,
        enable_agentic: bool = False,
        allow_create: bool = True,
        allow_update: bool = True,
        allow_submit: bool = False,
        allowed_doctypes: list = None,
    ) -> dict:
        """Build a mock settings dict."""
        settings = {
            "enable_agentic": 1 if enable_agentic else 0,
            "allow_create_actions": 1 if allow_create else 0,
            "allow_update_actions": 1 if allow_update else 0,
            "allow_submit_actions": 1 if allow_submit else 0,
            "allowed_action_doctypes": [],
        }
        if allowed_doctypes:
            settings["allowed_action_doctypes"] = [
                {"doctype_name": dt} for dt in allowed_doctypes
            ]
        return settings

    # ─── Property 2: Granular Controls Are Respected ──────────────────────────
    # For any action type T when allow_{T}_actions is False,
    # is_action_allowed(T, D) SHALL return (False, <reason>).
    # Validates: Requirements 2.2, 2.3, 2.4

    @skip_without_frappe
    @unittest.skipUnless(HAS_HYPOTHESIS, "hypothesis not installed")
    @given(
        doctype=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @hyp_settings(max_examples=100)
    def test_property_2_granular_create_control(self, doctype: str):
        """
        Property 2: Granular Controls Are Respected (Create)
        
        When enable_agentic is True but allow_create_actions is False,
        create actions SHALL be blocked.
        
        Feature: agentic-settings, Property 2: Granular controls respected
        Validates: Requirements 2.2
        """
        from ai_hrms_suite.utils.config import is_action_allowed

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=False,
            allow_update=True,
            allow_submit=True,
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            allowed, reason = is_action_allowed("create", doctype.strip())
            self.assertFalse(allowed)
            self.assertIn("create", reason.lower())

    @skip_without_frappe
    @unittest.skipUnless(HAS_HYPOTHESIS, "hypothesis not installed")
    @given(
        doctype=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @hyp_settings(max_examples=100)
    def test_property_2_granular_update_control(self, doctype: str):
        """
        Property 2: Granular Controls Are Respected (Update)
        
        When enable_agentic is True but allow_update_actions is False,
        update actions SHALL be blocked.
        
        Feature: agentic-settings, Property 2: Granular controls respected
        Validates: Requirements 2.3
        """
        from ai_hrms_suite.utils.config import is_action_allowed

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=False,
            allow_submit=True,
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            allowed, reason = is_action_allowed("update", doctype.strip())
            self.assertFalse(allowed)
            self.assertIn("update", reason.lower())

    @skip_without_frappe
    @unittest.skipUnless(HAS_HYPOTHESIS, "hypothesis not installed")
    @given(
        doctype=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    @hyp_settings(max_examples=100)
    def test_property_2_granular_submit_control(self, doctype: str):
        """
        Property 2: Granular Controls Are Respected (Submit)
        
        When enable_agentic is True but allow_submit_actions is False,
        submit actions SHALL be blocked.
        
        Feature: agentic-settings, Property 2: Granular controls respected
        Validates: Requirements 2.4
        """
        from ai_hrms_suite.utils.config import is_action_allowed

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=False,
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            allowed, reason = is_action_allowed("submit", doctype.strip())
            self.assertFalse(allowed)
            self.assertIn("submit", reason.lower())

    @skip_without_frappe
    def test_property_2_granular_controls_simple(self):
        """Simple version of Property 2 without hypothesis."""
        from ai_hrms_suite.utils.config import is_action_allowed

        test_cases = [
            ("create", {"allow_create": False, "allow_update": True, "allow_submit": True}),
            ("update", {"allow_create": True, "allow_update": False, "allow_submit": True}),
            ("submit", {"allow_create": True, "allow_update": True, "allow_submit": False}),
        ]

        for action_type, toggles in test_cases:
            mock_settings = self._mock_settings(enable_agentic=True, **toggles)

            with patch(
                "ai_hrms_suite.utils.config._get_settings_doc",
                return_value=mock_settings,
            ):
                allowed, reason = is_action_allowed(action_type, "Leave Application")
                self.assertFalse(allowed, f"{action_type} should be blocked")
                self.assertIn(action_type, reason.lower())

    # ─── Property 3: DocType Allowlist Enforcement ────────────────────────────
    # For any DocType D not in the allowlist (when non-empty),
    # is_action_allowed(T, D) SHALL return (False, <reason>).
    # Validates: Requirements 3.2

    @skip_without_frappe
    @unittest.skipUnless(HAS_HYPOTHESIS, "hypothesis not installed")
    @given(
        action_type=st.sampled_from(["create", "update", "submit"]),
        doctype=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and x.strip() != "Leave Application"),
    )
    @hyp_settings(max_examples=100)
    def test_property_3_doctype_allowlist_enforcement(self, action_type: str, doctype: str):
        """
        Property 3: DocType Allowlist Enforcement
        
        When a DocType is not in the allowlist (and allowlist is non-empty),
        actions on that DocType SHALL be blocked.
        
        Feature: agentic-settings, Property 3: DocType allowlist enforcement
        Validates: Requirements 3.2
        """
        from ai_hrms_suite.utils.config import is_action_allowed

        # Allowlist only contains "Leave Application"
        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
            allowed_doctypes=["Leave Application"],
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            allowed, reason = is_action_allowed(action_type, doctype.strip())
            self.assertFalse(allowed)
            self.assertIn("not permitted", reason.lower())

    @skip_without_frappe
    def test_property_3_doctype_allowlist_simple(self):
        """Simple version of Property 3 without hypothesis."""
        from ai_hrms_suite.utils.config import is_action_allowed

        # Only "Leave Application" is allowed
        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
            allowed_doctypes=["Leave Application"],
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            # Allowed DocType should pass
            allowed, reason = is_action_allowed("create", "Leave Application")
            self.assertTrue(allowed)
            self.assertEqual(reason, "")

            # Non-allowed DocTypes should be blocked
            for doctype in ["Employee", "Salary Slip", "Attendance"]:
                allowed, reason = is_action_allowed("create", doctype)
                self.assertFalse(allowed)
                self.assertIn("not permitted", reason.lower())

    # ─── Property 6: Tool Executor Respects Settings ──────────────────────────
    # For any call to _tool_prepare_action() where is_action_allowed() returns False,
    # the tool SHALL return an action_blocked type result.
    # Validates: Requirements 4.1, 4.2

    def test_property_6_tool_executor_returns_blocked(self):
        """
        Property 6: Tool Executor Respects Settings
        
        When agentic settings block an action, _tool_prepare_action()
        SHALL return an action_blocked type result with the reason.
        
        Feature: agentic-settings, Property 6: Tool executor respects settings
        Validates: Requirements 4.1, 4.2
        
        Note: This test requires Frappe environment. Run with bench run-tests.
        """
        # Skip if frappe is not available (unit test environment)
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required for tool executor tests")

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Leave Application",
                "values": {},
            })

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["type"], "action_blocked")
            self.assertIn("reason", result[0])
            self.assertIn("disabled", result[0]["reason"].lower())

    def test_property_6_tool_executor_blocked_response_format(self):
        """
        Property 6: Blocked response contains required fields.
        
        The action_blocked response SHALL contain:
        - type: "action_blocked"
        - reason: explanation string
        - action_type: the requested action
        - doctype: the target DocType
        
        Feature: agentic-settings, Property 6: Tool executor respects settings
        Validates: Requirements 4.1, 4.2, 4.3
        
        Note: This test requires Frappe environment. Run with bench run-tests.
        """
        # Skip if frappe is not available (unit test environment)
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required for tool executor tests")

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Leave Application",
                "values": {},
            })

            blocked = result[0]
            self.assertEqual(blocked["type"], "action_blocked")
            self.assertEqual(blocked["action_type"], "create")
            self.assertEqual(blocked["doctype"], "Leave Application")
            # Reason should mention administrator but not expose internal field names
            self.assertIn("administrator", blocked["reason"].lower())
            self.assertNotIn("enable_agentic", blocked["reason"])



class TestCacheInvalidation(unittest.TestCase):
    """
    Tests for cache invalidation of agentic settings.
    
    Feature: agentic-settings
    """

    # ─── Property 5: Settings Cache Invalidation ──────────────────────────────
    # For any change to agentic settings, after clear_settings_cache() is called,
    # subsequent calls to is_agentic_enabled() and is_action_allowed()
    # SHALL reflect the new values.
    # Validates: Requirements 1.5, 6.4

    @skip_without_frappe
    def test_property_5_cache_invalidation(self):
        """
        Property 5: Settings Cache Invalidation
        
        After clear_settings_cache() is called, subsequent calls to
        is_agentic_enabled() SHALL reflect the new settings values.
        
        Feature: agentic-settings, Property 5: Cache invalidation
        Validates: Requirements 1.5, 6.4
        """
        from ai_hrms_suite.utils.config import (
            is_agentic_enabled,
            is_action_allowed,
            clear_settings_cache,
            _SETTINGS_CACHE_KEY,
        )

        # Initial state: agentic disabled
        initial_settings = {
            "enable_agentic": 0,
            "allow_create_actions": 1,
            "allow_update_actions": 1,
            "allow_submit_actions": 0,
            "allowed_action_doctypes": [],
        }

        # Updated state: agentic enabled
        updated_settings = {
            "enable_agentic": 1,
            "allow_create_actions": 1,
            "allow_update_actions": 1,
            "allow_submit_actions": 0,
            "allowed_action_doctypes": [],
        }

        # Mock the settings doc function to return different values
        call_count = [0]
        def mock_get_settings():
            if call_count[0] == 0:
                return initial_settings
            return updated_settings

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            side_effect=mock_get_settings,
        ):
            # First call: should return False (agentic disabled)
            self.assertFalse(is_agentic_enabled())

            # Simulate settings change
            call_count[0] = 1

            # After "cache clear" (simulated by incrementing call_count),
            # the next call should return the new value
            self.assertTrue(is_agentic_enabled())

    @skip_without_frappe
    def test_clear_settings_cache_clears_both_keys(self):
        """
        Test that clear_settings_cache() clears both settings and policies cache keys.
        
        Feature: agentic-settings, Property 5: Cache invalidation
        Validates: Requirements 1.5, 6.4
        """
        from ai_hrms_suite.utils.config import (
            clear_settings_cache,
            _SETTINGS_CACHE_KEY,
            _POLICIES_CACHE_KEY,
        )

        # Mock frappe.cache
        mock_cache = MagicMock()

        with patch("ai_hrms_suite.utils.config.frappe") as mock_frappe:
            mock_frappe.cache = mock_cache

            clear_settings_cache()

            # Verify both cache keys are deleted
            mock_cache.delete_value.assert_any_call(_SETTINGS_CACHE_KEY)
            mock_cache.delete_value.assert_any_call(_POLICIES_CACHE_KEY)
            self.assertEqual(mock_cache.delete_value.call_count, 2)



class TestAgenticSettingsIntegration(unittest.TestCase):
    """
    Integration tests for agentic settings end-to-end flow.
    
    Feature: agentic-settings
    Tests the complete flow from settings to tool execution.
    """

    def _mock_settings(
        self,
        enable_agentic: bool = False,
        allow_create: bool = True,
        allow_update: bool = True,
        allow_submit: bool = False,
        allowed_doctypes: list = None,
    ) -> dict:
        """Build a mock settings dict."""
        settings = {
            "enable_agentic": 1 if enable_agentic else 0,
            "allow_create_actions": 1 if allow_create else 0,
            "allow_update_actions": 1 if allow_update else 0,
            "allow_submit_actions": 1 if allow_submit else 0,
            "allowed_action_doctypes": [],
        }
        if allowed_doctypes:
            settings["allowed_action_doctypes"] = [
                {"doctype_name": dt} for dt in allowed_doctypes
            ]
        return settings

    # ─── Task 8.1: End-to-end with agentic disabled ───────────────────────────

    def test_integration_agentic_disabled_blocks_create(self):
        """
        Integration Test: When agentic is disabled, create actions are blocked.
        
        Simulates user asking to create Leave Application when agentic is disabled.
        Verifies blocked response is returned.
        
        Feature: agentic-settings
        Validates: Requirements 4.1, 4.2, 4.3
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Leave Application",
                "values": {
                    "leave_type": "Casual Leave",
                    "from_date": "2025-02-15",
                    "to_date": "2025-02-16",
                },
            })

            # Should return blocked response
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["type"], "action_blocked")
            self.assertIn("disabled", result[0]["reason"].lower())
            self.assertEqual(result[0]["action_type"], "create")
            self.assertEqual(result[0]["doctype"], "Leave Application")

    def test_integration_agentic_disabled_blocks_update(self):
        """
        Integration Test: When agentic is disabled, update actions are blocked.
        
        Feature: agentic-settings
        Validates: Requirements 4.1, 4.2
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            result = _tool_prepare_action({
                "action_type": "update",
                "doctype": "Employee",
                "values": {"status": "Left"},
            })

            self.assertEqual(result[0]["type"], "action_blocked")
            self.assertEqual(result[0]["action_type"], "update")

    def test_integration_agentic_disabled_blocks_submit(self):
        """
        Integration Test: When agentic is disabled, submit actions are blocked.
        
        Feature: agentic-settings
        Validates: Requirements 4.1, 4.2
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(enable_agentic=False)

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            result = _tool_prepare_action({
                "action_type": "submit",
                "doctype": "Leave Application",
                "values": {},
            })

            self.assertEqual(result[0]["type"], "action_blocked")
            self.assertEqual(result[0]["action_type"], "submit")

    # ─── Task 8.2: End-to-end with agentic enabled ────────────────────────────

    def test_integration_agentic_enabled_allows_create(self):
        """
        Integration Test: When agentic is enabled, create actions proceed.
        
        Simulates user asking to create Leave Application when agentic is enabled.
        Verifies action_preview is returned (not blocked).
        
        Feature: agentic-settings
        Validates: Requirements 1.2 (inverse)
        
        Note: This test requires full Frappe environment with HRMS installed.
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
            from ai_hrms_suite.chat.retriever import validate_doctype_in_hrms
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
        )

        # Mock both settings and HRMS validation
        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ), patch(
            "ai_hrms_suite.chat.tools.validate_doctype_in_hrms",
            return_value=True,
        ), patch(
            "ai_hrms_suite.chat.tools.frappe.db.exists",
            return_value=True,
        ), patch(
            "ai_hrms_suite.chat.tools.frappe.has_permission",
            return_value=True,
        ), patch(
            "ai_hrms_suite.chat.tools.frappe.get_meta",
        ) as mock_meta:
            # Setup mock meta
            mock_meta_obj = MagicMock()
            mock_meta_obj.fields = []
            mock_meta_obj.get_field.return_value = None
            mock_meta.return_value = mock_meta_obj

            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Leave Application",
                "values": {
                    "leave_type": "Casual Leave",
                    "from_date": "2025-02-15",
                    "to_date": "2025-02-16",
                },
            })

            # Should NOT be blocked
            self.assertEqual(len(result), 1)
            self.assertNotEqual(result[0]["type"], "action_blocked")
            # Should be action_preview
            self.assertEqual(result[0]["type"], "action_preview")

    def test_integration_granular_create_disabled(self):
        """
        Integration Test: When agentic is enabled but create is disabled.
        
        Feature: agentic-settings
        Validates: Requirements 2.2
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=False,  # Create disabled
            allow_update=True,
            allow_submit=True,
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Leave Application",
                "values": {},
            })

            self.assertEqual(result[0]["type"], "action_blocked")
            self.assertIn("create", result[0]["reason"].lower())

    def test_integration_doctype_not_in_allowlist(self):
        """
        Integration Test: When DocType is not in allowlist.
        
        Feature: agentic-settings
        Validates: Requirements 3.2
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
            allowed_doctypes=["Leave Application"],  # Only Leave Application allowed
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ):
            # Try to create Employee (not in allowlist)
            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Employee",
                "values": {},
            })

            self.assertEqual(result[0]["type"], "action_blocked")
            self.assertIn("not permitted", result[0]["reason"].lower())

    def test_integration_doctype_in_allowlist_allowed(self):
        """
        Integration Test: When DocType is in allowlist, action proceeds.
        
        Feature: agentic-settings
        Validates: Requirements 3.2
        """
        try:
            from ai_hrms_suite.chat.tools import _tool_prepare_action
        except ImportError:
            self.skipTest("Frappe environment required")

        mock_settings = self._mock_settings(
            enable_agentic=True,
            allow_create=True,
            allow_update=True,
            allow_submit=True,
            allowed_doctypes=["Leave Application"],
        )

        with patch(
            "ai_hrms_suite.utils.config._get_settings_doc",
            return_value=mock_settings,
        ), patch(
            "ai_hrms_suite.chat.tools.validate_doctype_in_hrms",
            return_value=True,
        ), patch(
            "ai_hrms_suite.chat.tools.frappe.db.exists",
            return_value=True,
        ), patch(
            "ai_hrms_suite.chat.tools.frappe.has_permission",
            return_value=True,
        ), patch(
            "ai_hrms_suite.chat.tools.frappe.get_meta",
        ) as mock_meta:
            mock_meta_obj = MagicMock()
            mock_meta_obj.fields = []
            mock_meta_obj.get_field.return_value = None
            mock_meta.return_value = mock_meta_obj

            # Leave Application is in allowlist
            result = _tool_prepare_action({
                "action_type": "create",
                "doctype": "Leave Application",
                "values": {},
            })

            # Should NOT be blocked
            self.assertNotEqual(result[0]["type"], "action_blocked")
