from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SelectedPhone:
    id: str
    serial: str
    state: str
    transport: str
    transports: list[str]
    serials: dict[str, str]
    wifi_candidate_endpoint: str
    wifi_candidate_ip: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SelectedPhone":
        serials_raw = payload.get("serials")
        serials = serials_raw if isinstance(serials_raw, dict) else {}
        transports_raw = payload.get("transports")
        transports = transports_raw if isinstance(transports_raw, list) else []
        return cls(
            id=str(payload.get("id", "")),
            serial=str(payload.get("serial", "")),
            state=str(payload.get("state", "")),
            transport=str(payload.get("transport", "")),
            transports=[str(t) for t in transports],
            serials={str(k): str(v) for k, v in serials.items() if isinstance(v, str) and v},
            wifi_candidate_endpoint=str(payload.get("wifi_candidate_endpoint", "")),
            wifi_candidate_ip=str(payload.get("wifi_candidate_ip", "")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "serial": self.serial,
            "state": self.state,
            "transport": self.transport,
            "transports": list(self.transports),
            "serials": dict(self.serials),
            "wifi_candidate_endpoint": self.wifi_candidate_endpoint,
            "wifi_candidate_ip": self.wifi_candidate_ip,
        }
