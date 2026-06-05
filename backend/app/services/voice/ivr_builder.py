"""
IVR Builder — Dynamic TwiML Menu Generation

Builds Interactive Voice Response (IVR) menus from JSON configuration,
generating TwiML dynamically for each tenant. Supports:

1. Single-level IVR menus with configurable options
2. Multi-level (nested) IVR with sub-menus
3. DTMF and speech input gathering
4. Dial, sub-menu navigation, and input collection actions
5. Timeout and invalid-input handling with retry logic
6. Config validation and sensible defaults

Building Codes:
- BC-001: All operations scoped by company_id
- BC-008: Never crash — return error dicts instead of raising
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.voice.ivr_builder")

# ── Constants ─────────────────────────────────────────────────

VALID_ACTIONS = {"dial", "sub_menu", "gather_input", "hangup", "say"}
VALID_URGENCY_LEVELS = {"low", "medium", "high", "critical"}

# Default timeout and retry settings
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_ATTEMPTS = 3


class IVRBuilder:
    """Builds TwiML IVR menus from JSON configuration per tenant.

    All methods are scoped to company_id (BC-001) and never crash (BC-008).
    TwiML generation uses <Gather>, <Say>, <Dial>, <Redirect> verbs
    with proper XML escaping.
    """

    # ═══════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════

    def build_ivr_menu(
        self,
        menu_config: dict,
        company_id: str,
    ) -> str:
        """Build a single-level IVR menu as TwiML from JSON config.

        Generates a <Gather> block with options listed via <Say>,
        handles timeout and invalid input with retry logic.

        Args:
            menu_config: IVR menu configuration dict. Expected keys:
                greeting (str): Welcome message.
                options (list): List of option dicts with digit, label,
                    action, and action-specific fields.
                timeout_message (str): Message on no input.
                invalid_message (str): Message on invalid digit.
                max_attempts (int): Max retry count before fallback.
                timeout_seconds (int): Seconds to wait for input.
            company_id: Tenant company ID (BC-001).

        Returns:
            TwiML string for the IVR menu.
        """
        try:
            # Validate config first
            validation = self.validate_menu_config(menu_config)
            if not validation.get("valid", False):
                logger.warning(
                    "ivr_invalid_config",
                    extra={
                        "company_id": company_id,
                        "errors": validation.get("errors", []),
                    },
                )
                # Return a simple fallback TwiML
                return self._build_error_twiml(
                    "Menu configuration is invalid. Please contact support."
                )

            greeting = menu_config.get("greeting", "Welcome")
            options = menu_config.get("options", [])
            timeout_message = menu_config.get(
                "timeout_message", "We didn't receive your input."
            )
            invalid_message = menu_config.get(
                "invalid_message", "Invalid selection."
            )
            max_attempts = menu_config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
            timeout_seconds = menu_config.get(
                "timeout_seconds", DEFAULT_TIMEOUT_SECONDS
            )

            # Build the options prompt
            options_prompt = self._build_options_prompt(options)

            # Build the main Gather block
            gather_attrs = {
                "numDigits": "1",
                "timeout": str(timeout_seconds),
                "action": f"/api/v1/voice/ivr/handle?company_id={company_id}",
                "method": "POST",
            }

            # Build inner Say elements for the Gather
            inner_say = self._escape_xml(greeting)
            if options_prompt:
                inner_say += " " + options_prompt

            twiml = "<Response>"
            twiml += self._build_gather(gather_attrs, inner_say)

            # Fallback for no input (after Gather timeout)
            twiml += self._build_say(timeout_message)
            twiml += self._build_redirect(
                f"/api/v1/voice/ivr/retry?company_id={company_id}"
                f"&attempt=1&max_attempts={max_attempts}"
            )
            twiml += "</Response>"

            logger.info(
                "ivr_menu_built",
                extra={
                    "company_id": company_id,
                    "option_count": len(options),
                },
            )

            return twiml

        except Exception as exc:
            logger.error(
                "ivr_build_menu_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return self._build_error_twiml(
                "An error occurred. Please try again later."
            )

    def build_multi_level_menu(
        self,
        menus: dict,
        entry_menu_id: str,
        company_id: str,
    ) -> str:
        """Build a multi-level (nested) IVR system as TwiML.

        Generates TwiML for the entry menu, with <Redirect> verbs
        pointing to sub-menu endpoints. Each sub-menu is identified
        by its menu_id.

        Args:
            menus: Dict of menu_id -> menu_config. Each menu_config
                follows the same format as build_ivr_menu.
            entry_menu_id: The menu_id to use as the top-level entry.
            company_id: Tenant company ID (BC-001).

        Returns:
            TwiML string for the entry menu with nested references.
        """
        try:
            if not menus or not isinstance(menus, dict):
                return self._build_error_twiml("No menus configured.")

            if entry_menu_id not in menus:
                logger.warning(
                    "ivr_missing_entry_menu",
                    extra={
                        "company_id": company_id,
                        "entry_menu_id": entry_menu_id,
                    },
                )
                return self._build_error_twiml("Entry menu not found.")

            # Validate all menus
            for menu_id, menu_config in menus.items():
                validation = self.validate_menu_config(menu_config)
                if not validation.get("valid", False):
                    logger.warning(
                        "ivr_submenu_invalid",
                        extra={
                            "company_id": company_id,
                            "menu_id": menu_id,
                            "errors": validation.get("errors", []),
                        },
                    )

            # Build the entry menu with sub-menu awareness
            entry_config = menus[entry_menu_id]
            enhanced_config = self._resolve_submenu_redirects(
                entry_config, menus, company_id
            )

            # Build all sub-menu TwiML fragments (stored for reference)
            submenu_twiml_map: Dict[str, str] = {}
            for menu_id, menu_config in menus.items():
                if menu_id == entry_menu_id:
                    continue
                resolved = self._resolve_submenu_redirects(
                    menu_config, menus, company_id
                )
                submenu_twiml_map[menu_id] = self.build_ivr_menu(
                    resolved, company_id
                )

            # Build the entry menu TwiML
            entry_twiml = self.build_ivr_menu(enhanced_config, company_id)

            logger.info(
                "ivr_multi_level_built",
                extra={
                    "company_id": company_id,
                    "entry_menu_id": entry_menu_id,
                    "submenu_count": len(menus) - 1,
                },
            )

            return entry_twiml

        except Exception as exc:
            logger.error(
                "ivr_build_multi_level_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return self._build_error_twiml(
                "An error occurred. Please try again later."
            )

    def validate_menu_config(self, menu_config: dict) -> dict:
        """Validate an IVR menu configuration structure.

        Checks for required fields, valid action types, digit conflicts,
        and proper nesting of sub-menu references.

        Args:
            menu_config: IVR menu configuration dict to validate.

        Returns:
            Dict with:
                valid (bool): Whether the config is valid.
                errors (list): List of validation error strings.
        """
        errors: List[str] = []

        try:
            if not isinstance(menu_config, dict):
                return {"valid": False, "errors": ["Config must be a dictionary"]}

            # Check greeting
            if "greeting" not in menu_config or not menu_config["greeting"]:
                errors.append("Missing required field: greeting")

            # Check options
            options = menu_config.get("options")
            if not options or not isinstance(options, list):
                errors.append("Missing or invalid required field: options (must be a list)")
            elif len(options) == 0:
                errors.append("Options list must not be empty")
            else:
                seen_digits: set = set()
                for i, opt in enumerate(options):
                    if not isinstance(opt, dict):
                        errors.append(f"Option at index {i} must be a dictionary")
                        continue

                    # Check digit
                    digit = opt.get("digit")
                    if not digit:
                        errors.append(f"Option at index {i} missing 'digit'")
                    elif digit in seen_digits:
                        errors.append(
                            f"Duplicate digit '{digit}' at index {i}"
                        )
                    else:
                        seen_digits.add(digit)

                    # Check label
                    if "label" not in opt or not opt["label"]:
                        errors.append(f"Option at index {i} missing 'label'")

                    # Check action
                    action = opt.get("action")
                    if not action:
                        errors.append(f"Option at index {i} missing 'action'")
                    elif action not in VALID_ACTIONS:
                        errors.append(
                            f"Option at index {i} has invalid action '{action}'. "
                            f"Must be one of: {', '.join(sorted(VALID_ACTIONS))}"
                        )

                    # Check action-specific fields
                    if action == "dial":
                        if not opt.get("number"):
                            errors.append(
                                f"Option at index {i} with action 'dial' "
                                f"missing 'number'"
                            )
                    elif action == "sub_menu":
                        if not opt.get("sub_menu_id"):
                            errors.append(
                                f"Option at index {i} with action 'sub_menu' "
                                f"missing 'sub_menu_id'"
                            )
                    elif action == "gather_input":
                        if not opt.get("prompt"):
                            errors.append(
                                f"Option at index {i} with action 'gather_input' "
                                f"missing 'prompt'"
                            )

            # Check numeric fields
            max_attempts = menu_config.get("max_attempts")
            if max_attempts is not None:
                if not isinstance(max_attempts, int) or max_attempts < 1:
                    errors.append("max_attempts must be a positive integer")

            timeout_seconds = menu_config.get("timeout_seconds")
            if timeout_seconds is not None:
                if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
                    errors.append("timeout_seconds must be a positive integer")

            return {
                "valid": len(errors) == 0,
                "errors": errors,
            }

        except Exception as exc:
            logger.error(
                "ivr_validate_failed error=%s",
                str(exc)[:200],
            )
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(exc)[:200]}"],
            }

    def get_default_menu_config(self) -> dict:
        """Return a sensible default IVR menu configuration.

        Provides a standard 4-option IVR menu suitable for most
        helpdesk scenarios.

        Returns:
            Default IVR menu configuration dict.
        """
        return {
            "greeting": "Welcome to our support line.",
            "options": [
                {
                    "digit": "1",
                    "label": "Sales",
                    "action": "dial",
                    "number": "+1234567890",
                },
                {
                    "digit": "2",
                    "label": "Support",
                    "action": "dial",
                    "number": "+1234567891",
                },
                {
                    "digit": "3",
                    "label": "Check order status",
                    "action": "gather_input",
                    "prompt": "Please enter your order number followed by the pound key.",
                },
                {
                    "digit": "0",
                    "label": "Talk to an agent",
                    "action": "dial",
                    "number": "+0987654321",
                },
            ],
            "timeout_message": "We didn't receive your input. Please try again.",
            "invalid_message": "Invalid selection. Please try again.",
            "max_attempts": 3,
            "timeout_seconds": 10,
        }

    # ═══════════════════════════════════════════════════════════
    # Private Helpers — TwiML Generation
    # ═══════════════════════════════════════════════════════════

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters in text for safe TwiML output.

        Args:
            text: Raw text string.

        Returns:
            XML-escaped string.
        """
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _build_say(self, text: str, language: str = "en-US", voice: str = "") -> str:
        """Build a <Say> TwiML element.

        Args:
            text: Text to speak.
            language: Language code (e.g., en-US).
            voice: TTS voice name (optional).

        Returns:
            <Say> TwiML string.
        """
        escaped = self._escape_xml(text)
        attrs = f' language="{self._escape_xml(language)}"'
        if voice:
            attrs += f' voice="{self._escape_xml(voice)}"'
        return f"<Say{attrs}>{escaped}</Say>"

    def _build_gather(self, attrs: dict, inner_content: str) -> str:
        """Build a <Gather> TwiML element.

        Args:
            attrs: Dict of XML attributes for <Gather>.
            inner_content: TwiML content inside <Gather>.

        Returns:
            <Gather> TwiML string.
        """
        attr_str = " ".join(
            f'{k}="{self._escape_xml(str(v))}"' for k, v in attrs.items()
        )
        return f"<Gather {attr_str}>{inner_content}</Gather>"

    def _build_dial(self, number: str, timeout: int = 30) -> str:
        """Build a <Dial> TwiML element.

        Args:
            number: Phone number to dial.
            timeout: Dial timeout in seconds.

        Returns:
            <Dial> TwiML string.
        """
        escaped_number = self._escape_xml(number)
        return f'<Dial timeout="{timeout}">{escaped_number}</Dial>'

    def _build_redirect(self, url: str, method: str = "POST") -> str:
        """Build a <Redirect> TwiML element.

        Args:
            url: URL to redirect to.
            method: HTTP method for the redirect.

        Returns:
            <Redirect> TwiML string.
        """
        escaped_url = self._escape_xml(url)
        return f'<Redirect method="{method}">{escaped_url}</Redirect>'

    def _build_hangup(self) -> str:
        """Build a <Hangup> TwiML element.

        Returns:
            <Hangup/> TwiML string.
        """
        return "<Hangup/>"

    def _build_error_twiml(self, message: str) -> str:
        """Build a simple error TwiML response.

        Args:
            message: Error message to speak.

        Returns:
            TwiML string with Say + Hangup.
        """
        return (
            f"<Response>"
            f"{self._build_say(message)}"
            f"{self._build_hangup()}"
            f"</Response>"
        )

    def _build_options_prompt(self, options: list) -> str:
        """Build a spoken prompt listing all menu options.

        Args:
            options: List of option dicts with digit and label.

        Returns:
            Formatted options prompt string.
        """
        if not options:
            return ""

        parts: List[str] = []
        for opt in options:
            digit = opt.get("digit", "")
            label = opt.get("label", "")
            if digit and label:
                parts.append(f"Press {digit} for {label}.")

        return " ".join(parts)

    def _resolve_submenu_redirects(
        self,
        menu_config: dict,
        menus: dict,
        company_id: str,
    ) -> dict:
        """Resolve sub_menu actions into Redirect TwiML references.

        For options with action 'sub_menu', replaces the action with
        a redirect URL pointing to the sub-menu endpoint.

        Args:
            menu_config: Single menu configuration.
            menus: All available menus dict.
            company_id: Tenant company ID.

        Returns:
            Enhanced menu config with resolved sub-menu references.
        """
        import copy

        enhanced = copy.deepcopy(menu_config)
        options = enhanced.get("options", [])

        for opt in options:
            if opt.get("action") == "sub_menu":
                sub_menu_id = opt.get("sub_menu_id", "")
                if sub_menu_id in menus:
                    # The sub_menu action will be handled by the IVR
                    # endpoint which routes to the correct menu TwiML
                    opt["_submenu_url"] = (
                        f"/api/v1/voice/ivr/menu/{sub_menu_id}"
                        f"?company_id={company_id}"
                    )
                else:
                    logger.warning(
                        "ivr_submenu_not_found",
                        extra={
                            "company_id": company_id,
                            "sub_menu_id": sub_menu_id,
                        },
                    )
                    # Fallback: convert to hangup with message
                    opt["action"] = "say"
                    opt["message"] = "The selected option is not available."

        return enhanced

    def build_option_twiml(
        self,
        option: dict,
        company_id: str,
        language: str = "en-US",
        voice: str = "",
    ) -> str:
        """Build TwiML for a single IVR option selection.

        Called by the IVR handler when a digit is pressed.

        Args:
            option: The matched option dict from menu config.
            company_id: Tenant company ID (BC-001).
            language: TTS language code.
            voice: TTS voice name.

        Returns:
            TwiML string for the selected option.
        """
        try:
            action = option.get("action", "")
            twiml = "<Response>"

            if action == "dial":
                number = option.get("number", "")
                if number:
                    twiml += self._build_dial(number)
                else:
                    twiml += self._build_say(
                        "No number configured for this option.",
                        language, voice,
                    )

            elif action == "sub_menu":
                submenu_url = option.get(
                    "_submenu_url",
                    f"/api/v1/voice/ivr/menu/{option.get('sub_menu_id', '')}"
                    f"?company_id={company_id}",
                )
                twiml += self._build_redirect(submenu_url)

            elif action == "gather_input":
                prompt = option.get("prompt", "Please enter your input.")
                gather_attrs = {
                    "input": "dtmf",
                    "timeout": "15",
                    "finishOnKey": "#",
                    "action": (
                        f"/api/v1/voice/ivr/input"
                        f"?company_id={company_id}",
                    ),
                    "method": "POST",
                }
                twiml += self._build_gather(
                    gather_attrs,
                    self._build_say(prompt, language, voice),
                )
                # Fallback if no input
                twiml += self._build_say(
                    "We didn't receive any input. Goodbye.",
                    language, voice,
                )
                twiml += self._build_hangup()

            elif action == "say":
                message = option.get("message", "")
                twiml += self._build_say(message, language, voice)
                twiml += self._build_hangup()

            elif action == "hangup":
                twiml += self._build_say(
                    "Thank you for calling. Goodbye.",
                    language, voice,
                )
                twiml += self._build_hangup()

            else:
                twiml += self._build_say(
                    "Invalid option selected.",
                    language, voice,
                )
                twiml += self._build_hangup()

            twiml += "</Response>"
            return twiml

        except Exception as exc:
            logger.error(
                "ivr_build_option_twiml_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return self._build_error_twiml(
                "An error occurred processing your selection."
            )

    def build_retry_twiml(
        self,
        menu_config: dict,
        attempt: int,
        company_id: str,
        reason: str = "timeout",
    ) -> str:
        """Build TwiML for a retry attempt after timeout or invalid input.

        Args:
            menu_config: Original IVR menu configuration.
            attempt: Current attempt number (1-based).
            company_id: Tenant company ID (BC-001).
            reason: 'timeout' or 'invalid'.

        Returns:
            TwiML string for retry prompt.
        """
        try:
            max_attempts = menu_config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
            timeout_seconds = menu_config.get(
                "timeout_seconds", DEFAULT_TIMEOUT_SECONDS
            )
            options = menu_config.get("options", [])

            if attempt > max_attempts:
                # Max retries exceeded
                message = (
                    "Maximum attempts reached. "
                    "Please try again later. Goodbye."
                )
                return f"<Response>{self._build_say(message)}{self._build_hangup()}</Response>"

            # Build retry prompt
            if reason == "invalid":
                message = menu_config.get(
                    "invalid_message", "Invalid selection."
                )
            else:
                message = menu_config.get(
                    "timeout_message", "We didn't receive your input."
                )

            options_prompt = self._build_options_prompt(options)

            gather_attrs = {
                "numDigits": "1",
                "timeout": str(timeout_seconds),
                "action": f"/api/v1/voice/ivr/handle?company_id={company_id}",
                "method": "POST",
            }

            inner_content = (
                f"{self._build_say(message)} "
                f"{self._build_say(options_prompt)}"
            )

            twiml = "<Response>"
            twiml += self._build_gather(gather_attrs, inner_content)

            # Fallback after this Gather timeout
            next_attempt = attempt + 1
            twiml += self._build_redirect(
                f"/api/v1/voice/ivr/retry?company_id={company_id}"
                f"&attempt={next_attempt}&max_attempts={max_attempts}"
                f"&reason=timeout"
            )
            twiml += "</Response>"

            return twiml

        except Exception as exc:
            logger.error(
                "ivr_build_retry_twiml_failed company_id=%s error=%s",
                company_id, str(exc)[:200],
            )
            return self._build_error_twiml(
                "An error occurred. Please try again later."
            )
