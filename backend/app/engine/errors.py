"""Domain errors raised by the deterministic game engine."""


class EngineError(ValueError):
    """Base class for errors safe to expose as a bad player action."""


class InvalidAction(EngineError):
    """The requested action is not available in the current state."""


class InvalidEffect(EngineError):
    """An event contains an unsupported or unsafe state mutation."""


class ConfigurationError(EngineError):
    """Content configuration cannot be loaded safely."""
