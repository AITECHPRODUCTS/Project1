class VerificationRequiredError(RuntimeError):
    def __init__(self, message: str, *, action: str = "verification") -> None:
        super().__init__(message); self.action = action

class IntegrationNotConfiguredError(RuntimeError): pass
class ResourceBudgetExceeded(RuntimeError): pass
