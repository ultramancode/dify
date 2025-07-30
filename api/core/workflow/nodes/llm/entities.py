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

            auto: Smart default
                    If <think>…</think> blocks exist, strip the tags and move the inner text to
                    `reasoning_content`. If no tags are present, leave the original text unchanged 
                    and omit `reasoning_content` field.

            legacy: Leave <think> tags intact; never set `reasoning_content`. 
                    Use this for strict backward compatibility.

            field : Always return a `reasoning_content` field. 
                    If <think> tags are present, strip them and use the inner text;  
                    if no tags are present, an empty string is returned.
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
