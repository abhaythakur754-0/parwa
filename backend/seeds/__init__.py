"""Backend seeds module."""

from .seed_clients_031_050 import (
    ClientSeed,
    CLIENTS_031_050,
    get_all_clients,
    get_client_by_id,
    get_clients_by_variant,
    get_clients_by_industry,
    get_total_stats,
    validate_all_clients,
)

__all__ = [
    "ClientSeed",
    "CLIENTS_031_050",
    "get_all_clients",
    "get_client_by_id",
    "get_clients_by_variant",
    "get_clients_by_industry",
    "get_total_stats",
    "validate_all_clients",
]
