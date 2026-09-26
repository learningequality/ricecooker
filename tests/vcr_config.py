import json

import pytest

try:
    import vcr

    my_vcr = vcr.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode="none",
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        filter_headers=["authorization"],
    )

    def _scrub_box_access_token(response):
        try:
            body = json.loads(response["body"]["string"])
        except (TypeError, ValueError):
            return response
        if isinstance(body, dict) and "access_token" in body:
            body["access_token"] = "FILTERED"
            response["body"]["string"] = json.dumps(body).encode("utf-8")
        return response

    # Box's client credentials grant sends the enterprise id as box_subject_id.
    box_vcr = vcr.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode="once",
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        filter_headers=["authorization"],
        filter_post_data_parameters=["client_id", "client_secret", "box_subject_id"],
        before_record_response=_scrub_box_access_token,
        decode_compressed_response=True,
    )
except ImportError:

    class VCR:
        def use_cassette(self, *args, **kwargs):
            return pytest.mark.skip("vcrpy is not available on this Python version")

    my_vcr = VCR()
    box_vcr = VCR()
