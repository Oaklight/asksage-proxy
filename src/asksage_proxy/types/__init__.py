"""Type definitions for AskSage Proxy."""

from .chat_completion import (
    FINISH_REASONS,
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionMessageCore,
    ChoiceCore,
    ChoiceDelta,
    NonStreamChoice,
    StreamChoice,
)
from .completions import CompletionUsage
from .function_call import (
    ChatCompletionMessageToolCall,
    ChatCompletionNamedToolChoiceParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionToolParam,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
    Function,
    FunctionDefinition,
    FunctionDefinitionCore,
)

__all__ = [
    # Chat completion types
    "FINISH_REASONS",
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatCompletionMessage",
    "ChatCompletionMessageCore",
    "ChoiceCore",
    "ChoiceDelta",
    "NonStreamChoice",
    "StreamChoice",
    # Completion usage
    "CompletionUsage",
    # Function call types
    "ChatCompletionMessageToolCall",
    "ChatCompletionNamedToolChoiceParam",
    "ChatCompletionToolChoiceOptionParam",
    "ChatCompletionToolParam",
    "ChoiceDeltaToolCall",
    "ChoiceDeltaToolCallFunction",
    "Function",
    "FunctionDefinition",
    "FunctionDefinitionCore",
]