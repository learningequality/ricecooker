""" Tests for license getting and serialization """

import json
import pytest

from le_utils.constants.licenses import (
    CC_BY, CC_BY_SA, CC_BY_ND, CC_BY_NC, CC_BY_NC_SA, CC_BY_NC_ND,
    ALL_RIGHTS_RESERVED,
    PUBLIC_DOMAIN,
    SPECIAL_PERMISSIONS
)
from ricecooker.classes.licenses import get_license



""" *********** LICENSE FIXTURES *********** """
@pytest.fixture
def license_objects():
    regular_ids = [CC_BY, CC_BY_SA, CC_BY_ND, CC_BY_NC, CC_BY_NC_SA, CC_BY_NC_ND,
                   ALL_RIGHTS_RESERVED, PUBLIC_DOMAIN]
    license_objects = []
    for regular_id in regular_ids:
        # with desciption and copyright_holder
        licence_obj = get_license(regular_id,
                                   copyright_holder='Some name',
                                   description='Le description')
        assert licence_obj, 'licence_obj should exist'
        license_objects.append(licence_obj)

        # with desciption only
        licence_obj = get_license(regular_id, description='Le description solo2')
        assert licence_obj, 'licence_obj should exist'
        license_objects.append(licence_obj)

        # with copyright_holder only
        licence_obj = get_license(regular_id, copyright_holder='Some name3')
        assert licence_obj, 'licence_obj should exist'
        license_objects.append(licence_obj)

        # bare
        licence_obj = get_license(regular_id)
        assert licence_obj, 'licence_obj should exist'
        license_objects.append(licence_obj)

    return license_objects

@pytest.fixture
def special_license():
    return get_license(SPECIAL_PERMISSIONS,
                       copyright_holder='Authorov',
                       description='Only for use offline')





""" *********** LICENSE TESTS *********** """

def test_the_license_fixtures(license_objects, special_license):
    assert len(license_objects) > 4
    assert special_license.license_id == SPECIAL_PERMISSIONS
    assert special_license.description


def test_bad_special_license():
    try:
        get_license(SPECIAL_PERMISSIONS, description=None)
        assert False, 'Should not come here because of missing description'
    except AssertionError:
        assert True, 'SPECIAL_PERMISSIONS without description should raise an exception'


def _compare_licence_objects(obj1, obj2):
    same = True
    if not obj1.license_id == obj2.license_id:
        same = False
    if not obj1.description == obj2.description:
        same = False
    if not obj1.copyright_holder == obj2.copyright_holder:
        same = False
    return same


def test_license_serilizibility(license_objects, special_license):
    orig_licenses = license_objects
    orig_licenses.append(special_license)
    for licence_orig in orig_licenses:
        # serizlize
        license_dict = licence_orig.as_dict()
        license_json = json.dumps(license_dict)
        # deserizlize
        license_copy_dict = json.loads(license_json)
        license_copy = get_license(**license_copy_dict)

        same_attributes = _compare_licence_objects(licence_orig, license_copy)
        assert same_attributes, 'License attributes not the same after serizlize'

