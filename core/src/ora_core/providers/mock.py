from __future__ import annotations

from .contracts import ProviderCapabilities, ProviderRequest, ProviderResponse, ProviderStatus


class MockProviderAdapter:
    provider_id = "mock"
    capabilities = ProviderCapabilities(
        chat=True,
        structured_output=True,
        streaming=False,
        vision=False,
        tool_use=False,
        local_only=False,
        cloud=False,
        external_provider=False,
    )

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            configured=True,
            available=True,
            reason=None,
            capabilities=self.capabilities,
        )

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        del request, allow_live_call
        return ProviderResponse(
            provider=self.provider_id,
            model="mock-deterministic",
            output_text="YonerAI mock provider response. No live provider call was made.",
            deterministic=True,
        )
