"""Needle 3 conversation agent.

Default exposure, stated: Needle receives exactly what Home Assistant's LLM API hands any
model: the API's own tools as JSON schema (Needle's built-in retrieval shows it the top five
per turn) and the API's own system prompt as its system facts. Needle's own defaults are kept:
no confidence threshold beyond the engine's, no triggers, no tool renaming. Every call Needle
makes is executed through the LLM API, exactly as for the Ollama integration.

ONE TURN per request: Needle generates no text, so there is no answer to wait for after a tool
runs. Its documented multi-turn pattern (feed each result back through complete()) was tried
on datasets/assist debug cases and Needle read Home Assistant's tool result as a new request
and acted again, undoing its own first call. So one complete() per utterance, and every call
it returns in that turn is executed; a request for two actions still gets two calls.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from probatio import to_openapi

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

DOMAIN = "hometiny_needle"
NO_ACTION_REPLY = "Sorry, I could not find an action for that."
DONE_REPLY = "Done."

_LOGGER = logging.getLogger(__name__)


def _tool_schema(tool: llm.Tool, serializer: Any) -> dict[str, Any]:
    """Render one LLM API tool in the raw JSON-schema form Needle consumes."""
    spec: dict[str, Any] = {
        "name": tool.name,
        "parameters": to_openapi(tool.parameters, custom_serializer=serializer),
    }
    if tool.description:
        spec["description"] = tool.description
    return spec


def _needle_turn(tools: list[dict[str, Any]], system: str, text: str) -> dict[str, Any]:
    """Run in an executor: a fresh Needle session per request, one toolset, one turn."""
    import needle  # noqa: PLC0415  heavy import, loaded on first use

    return needle.Needle(tools=tools, system=system or None).complete(text)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the conversation entity."""
    async_add_entities([NeedleConversationEntity(entry)])


class NeedleConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Needle 3 driven through Home Assistant's LLM API."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Cactus Compute",
            model="needle3",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return the supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register as a conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the agent."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Answer one utterance."""
        settings = {**self.entry.data, **self.entry.options}
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                settings.get(CONF_LLM_HASS_API),
                settings.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        tools: list[dict[str, Any]] = []
        if chat_log.llm_api:
            serializer = chat_log.llm_api.custom_serializer
            tools = [_tool_schema(t, serializer) for t in chat_log.llm_api.tools]
        system = chat_log.content[0].content if chat_log.content else ""

        try:
            reply = await self.hass.async_add_executor_job(
                _needle_turn, tools, system, user_input.text
            )
        except Exception as err:  # noqa: BLE001  recorded in the response, counted as out of range
            reply = {"success": False, "error_code": type(err).__name__, "error": str(err)[:300]}
        _LOGGER.debug("Needle turn: %s", reply)

        engine_error = None
        calls: list[dict[str, Any]] = []
        if reply.get("success") is False:
            # Recorded in the task's response so out-of-range cases are counted, never silently scored.
            engine_error = f"Needle error: {reply.get('error_code')}: {reply.get('error')}"
        elif reply.get("type") == "call":
            calls = reply.get("function_calls") or []
        if calls:
            async for _result in chat_log.async_add_assistant_content(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    tool_calls=[
                        llm.ToolInput(tool_name=call["name"], tool_args=call.get("arguments") or {})
                        for call in calls
                    ],
                )
            ):
                pass
        acted = bool(calls)

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=self.entity_id,
                content=engine_error or (DONE_REPLY if acted else NO_ACTION_REPLY),
            )
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
