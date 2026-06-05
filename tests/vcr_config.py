import json

import pytest

try:
    import vcr

    my_vcr = vcr.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode="new_episodes",
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        filter_headers=["authorization"],
    )

    def _scrub_box_response(response):
        """Scrub OAuth access tokens and account identity from recorded JSON response bodies."""
        try:
            body = json.loads(response["body"]["string"])
        except (KeyError, TypeError, ValueError, UnicodeDecodeError):
            return response
        if not isinstance(body, dict):
            return response
        changed = False
        if "access_token" in body:
            body["access_token"] = "FILTERED"
            changed = True
        # File info responses embed the owning account's user id, name,
        # and email in these entity fields.
        for entity_key in ("created_by", "modified_by", "owned_by"):
            user = body.get(entity_key)
            if isinstance(user, dict):
                for field in ("id", "name", "login"):
                    if field in user:
                        user[field] = "FILTERED"
                changed = True
        if changed:
            response["body"]["string"] = json.dumps(body).encode("utf-8")
        return response

    # Box's client credentials grant sends the client id/secret in the POST
    # body and returns an access token in the response, so both need
    # filtering in addition to the authorization header.
    # box_subject_id carries the enterprise ID in the CCG token request.
    # decode_compressed_response ensures _scrub_box_response always sees
    # plain JSON even if the token response is gzipped.
    box_vcr = vcr.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode="new_episodes",
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        filter_headers=["authorization"],
        filter_post_data_parameters=["client_id", "client_secret", "box_subject_id"],
        before_record_response=_scrub_box_response,
        decode_compressed_response=True,
    )
except ImportError:

    class VCR:
        def use_cassette(self, *args, **kwargs):
            return pytest.mark.skip("vcrpy is not available on this Python version")

    my_vcr = VCR()
    box_vcr = VCR()
