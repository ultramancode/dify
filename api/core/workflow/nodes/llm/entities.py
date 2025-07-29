from collections.abc import Mapping, Sequence
from typing import Any, Optional, Literal

from pydantic import BaseModel, Field, field_validator

from core.model_runtime.entities import ImagePromptMessageContent, LLMMode
from core.prompt.entities.advanced_prompt_entities import ChatModelMessage, CompletionModelPromptTemplate, MemoryConfig
from core.workflow.entities.variable_entities import VariableSelector
from core.workflow.nodes.base import BaseNodeData


class ModelConfig(BaseModel):
    provider: str
    name: str
    mode: LLMMode
    completion_params: dict[str, Any] = {}


class ContextConfig(BaseModel):
    enabled: bool
    variable_selector: Optional[list[str]] = None


class VisionConfigOptions(BaseModel):
    variable_selector: Sequence[str] = Field(default_factory=lambda: ["sys", "files"])
    detail: ImagePromptMessageContent.DETAIL = ImagePromptMessageContent.DETAIL.HIGH


class VisionConfig(BaseModel):
    enabled: bool = False
    configs: VisionConfigOptions = Field(default_factory=VisionConfigOptions)

    @field_validator("configs", mode="before")
    @classmethod
    def convert_none_configs(cls, v: Any):
        if v is None:
            return VisionConfigOptions()
        return v


class PromptConfig(BaseModel):
    jinja2_variables: Sequence[VariableSelector] = Field(default_factory=list)

    @field_validator("jinja2_variables", mode="before")
    @classmethod
    def convert_none_jinja2_variables(cls, v: Any):
        if v is None:
            return []
        return v


class LLMNodeChatModelMessage(ChatModelMessage):
    text: str = ""
    jinja2_text: Optional[str] = None


class LLMNodeCompletionModelPromptTemplate(CompletionModelPromptTemplate):
    jinja2_text: Optional[str] = None


class LLMNodeData(BaseNodeData):
    model: ModelConfig
    prompt_template: Sequence[LLMNodeChatModelMessage] | LLMNodeCompletionModelPromptTemplate
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    memory: Optional[MemoryConfig] = None
    context: ContextConfig
    vision: VisionConfig = Field(default_factory=VisionConfig)
    structured_output: Mapping[str, Any] | None = None
    # We used 'structured_output_enabled' in the past, but it's not a good name.
    structured_output_switch_on: bool = Field(False, alias="structured_output_enabled")
    reasoning_format: Literal["auto", "legacy", "field"] = Field(
        default="auto",
        description=(
            """
            Strategy for handling model reasoning output.

            auto : Detects the output form and applies the safest rule
                    1) If the model returns a `reasoning_content` field, keep it.
                    2) Else if <think>…</think> blocks are found, strip the tags
                        and move their inner text to `reasoning_content`.
                    3) Else (no tags, no field) keep the original text unchanged.

            legacy : Always leave <think> tags in the text; no `reasoning_content`
                    field is set, for maximum backward compatibility.

            field : Always strip <think> tags (if any) and expose their inner text
                    through `reasoning_content`, while returning the cleaned text
                    as the main output.
            """
        )
    )

    @field_validator("prompt_config", mode="before")
    @classmethod
    def convert_none_prompt_config(cls, v: Any):
        if v is None:
            return PromptConfig()
        return v

    @property
    def structured_output_enabled(self) -> bool:
        return self.structured_output_switch_on and self.structured_output is not None
