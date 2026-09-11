import itertools

import pytest

from ai_core.privacy import DataClass, OutboundForm, is_egress_eligible
from ai_core.provider_catalog import NetworkBoundary


GOVERNED_BOUNDARIES = (
    NetworkBoundary.LOCAL_SAME_HOST,
    NetworkBoundary.EXTERNAL,
    NetworkBoundary.UNKNOWN_BOUNDARY,
)


def test_privacy_vocabularies_are_exact() -> None:
    assert [data_class.value for data_class in DataClass] == [
        "synthetic",
        "public_no_pii",
        "public_possible_pii",
        "private_client_data",
        "secret",
    ]
    assert [outbound_form.value for outbound_form in OutboundForm] == [
        "raw",
        "sanitized",
        "surrogated",
    ]


@pytest.mark.parametrize(
    ("outbound_form", "network_boundary"),
    itertools.product(OutboundForm, GOVERNED_BOUNDARIES),
)
def test_secret_is_denied_for_every_form_and_boundary(
    outbound_form: OutboundForm,
    network_boundary: NetworkBoundary,
) -> None:
    assert not is_egress_eligible(
        data_class=DataClass.SECRET,
        outbound_form=outbound_form,
        network_boundary=network_boundary,
        request_egress_authorized=True,
    )


@pytest.mark.parametrize(
    "outbound_form",
    (OutboundForm.SANITIZED, OutboundForm.SURROGATED),
)
def test_transformation_does_not_reclassify_secret(
    outbound_form: OutboundForm,
) -> None:
    assert not is_egress_eligible(
        data_class=DataClass.SECRET,
        outbound_form=outbound_form,
        network_boundary=NetworkBoundary.EXTERNAL,
        request_egress_authorized=True,
    )


@pytest.mark.parametrize(
    "network_boundary",
    (NetworkBoundary.EXTERNAL, NetworkBoundary.UNKNOWN_BOUNDARY),
)
def test_missing_request_authorization_denies_non_local_egress(
    network_boundary: NetworkBoundary,
) -> None:
    assert not is_egress_eligible(
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.SANITIZED,
        network_boundary=network_boundary,
    )


@pytest.mark.parametrize(
    "network_boundary",
    (NetworkBoundary.EXTERNAL, NetworkBoundary.UNKNOWN_BOUNDARY),
)
def test_explicit_request_authorization_allows_non_secret_egress(
    network_boundary: NetworkBoundary,
) -> None:
    assert is_egress_eligible(
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.SANITIZED,
        network_boundary=network_boundary,
        request_egress_authorized=True,
    )


def test_non_secret_same_host_data_does_not_require_egress_authorization() -> None:
    assert is_egress_eligible(
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.RAW,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
    )
