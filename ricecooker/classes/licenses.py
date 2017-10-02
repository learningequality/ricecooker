# License models

from ..exceptions import UnknownLicenseError
from .. import config
from le_utils.constants import licenses


def get_license(license_id, copyright_holder=None, description=None):
    if license_id == licenses.CC_BY:
        return CC_BYLicense(copyright_holder=copyright_holder)
    elif license_id == licenses.CC_BY_SA:
        return CC_BY_SALicense(copyright_holder=copyright_holder)
    elif license_id == licenses.CC_BY_ND:
        return CC_BY_NDLicense(copyright_holder=copyright_holder)
    elif license_id == licenses.CC_BY_NC:
        return CC_BY_NCLicense(copyright_holder=copyright_holder)
    elif license_id == licenses.CC_BY_NC_SA:
        return CC_BY_NC_SALicense(copyright_holder=copyright_holder)
    elif license_id == licenses.CC_BY_NC_ND:
        return CC_BY_NC_NDLicense(copyright_holder=copyright_holder)
    elif license_id == licenses.ALL_RIGHTS_RESERVED:
        return AllRightsLicense(copyright_holder=copyright_holder)
    elif license_id == licenses.PUBLIC_DOMAIN:
        return PublicDomainLicense(copyright_holder=copyright_holder)
    elif license_id == licenses.SPECIAL_PERMISSIONS:
        return SpecialPermissionsLicense(copyright_holder=copyright_holder, description=description)
    else:
        raise UnknownLicenseError("{} is not a valid license id. (Valid license are {})".format(license_id, [l[0] for l in licenses.choices]))


class License(object):
    license_id = None # (str): content's license based on le_utils.constants.licenses
    copyright_holder = None # (str): name of person or organization who owns license (optional)
    description = None # (str): description of the license (optional)
    require_copyright_holder = True

    def __init__(self, copyright_holder=None, description=None):
        self.copyright_holder = copyright_holder or ""
        self.description = description

    def get_id(self):
        return self.license_id

    def validate(self):
        assert not self.require_copyright_holder or self.copyright_holder != "", "Assertion Failed: {} License requires a copyright holder".format(self.license_id)
        assert isinstance(self.copyright_holder, str), "Assertion Failed: Copyright holder must be a string"

    def truncate_fields(self):
        if self.description and len(self.description) > config.MAX_LICENSE_DESCRIPTION_LENGTH:
            config.print_truncate("license_description", self.license_id, self.description)
            self.description = self.description[:config.MAX_LICENSE_DESCRIPTION_LENGTH]

        if self.copyright_holder and len(self.copyright_holder) > config.MAX_COPYRIGHT_HOLDER_LENGTH:
            config.print_truncate("copyright_holder", self.license_id, self.copyright_holder)
            self.copyright_holder = self.copyright_holder[:config.MAX_COPYRIGHT_HOLDER_LENGTH]

    def as_dict(self):
        return {'license_id': self.license_id,
                'copyright_holder': self.copyright_holder,
                'description': self.description }

class CC_BYLicense(License):
    """
        The Attribution License lets others distribute, remix, tweak,
        and build upon your work, even commercially, as long as they credit
        you for the original creation. This is the most accommodating of
        licenses offered. Recommended for maximum dissemination and use of
        licensed materials.

        Reference: https://creativecommons.org/licenses/by/4.0
    """
    license_id = licenses.CC_BY

class CC_BY_SALicense(License):
    """
        The Attribution-ShareAlike License lets others remix, tweak, and
        build upon your work even for commercial purposes, as long as they
        credit you and license their new creations under the identical terms.
        This license is often compared to "copyleft" free and open source
        software licenses. All new works based on yours will carry the same
        license, so any derivatives will also allow commercial use. This is
        the license used by Wikipedia, and is recommended for materials that
        would benefit from incorporating content from Wikipedia and similarly
        licensed projects.

        Reference: https://creativecommons.org/licenses/by-sa/4.0
    """
    license_id = licenses.CC_BY_SA

class CC_BY_NDLicense(License):
    """
        The Attribution-NoDerivs License allows for redistribution, commercial
        and non-commercial, as long as it is passed along unchanged and in
        whole, with credit to you.

        Reference: https://creativecommons.org/licenses/by-nd/4.0
    """
    license_id = licenses.CC_BY_ND

class CC_BY_NCLicense(License):
    """
        The Attribution-NonCommercial License lets others remix, tweak, and
        build upon your work non-commercially, and although their new works
        must also acknowledge you and be non-commercial, they don't have to
        license their derivative works on the same terms.

        Reference: https://creativecommons.org/licenses/by-nc/4.0
    """
    license_id = licenses.CC_BY_NC

class CC_BY_NC_SALicense(License):
    """
        The Attribution-NonCommercial-ShareAlike License lets others remix, tweak,
        and build upon your work non-commercially, as long as they credit you and
        license their new creations under the identical terms.

        Reference: https://creativecommons.org/licenses/by-nc-sa/4.0
    """
    license_id = licenses.CC_BY_NC_SA

class CC_BY_NC_NDLicense(License):
    """
        The Attribution-NonCommercial-NoDerivs License is the most restrictive of
        our six main licenses, only allowing others to download your works and share
        them with others as long as they credit you, but they can't change them in
        any way or use them commercially.

        Reference: https://creativecommons.org/licenses/by-nc-nd/4.0
    """
    license_id = licenses.CC_BY_NC_ND

class AllRightsLicense(License):
    """
        The All Rights Reserved License indicates that the copyright holder reserves,
        or holds for their own use, all the rights provided by copyright law under
        one specific copyright treaty.

        Reference: http://www.allrights-reserved.com
    """
    license_id = licenses.ALL_RIGHTS_RESERVED

class PublicDomainLicense(License):
    """
        Public Domain work has been identified as being free of known restrictions
        under copyright law, including all related and neighboring rights.

        Reference: https://creativecommons.org/publicdomain/mark/1.0
    """
    require_copyright_holder = False
    license_id = licenses.PUBLIC_DOMAIN

class SpecialPermissionsLicense(License):
    """
        Special Permissions is a custom license to use when the current licenses
        do not apply to the content. The owner of this license is responsible for
        creating a description of what this license entails.
    """
    license_id = licenses.SPECIAL_PERMISSIONS

    def __init__(self, copyright_holder=None, description=None):
        assert description, "Special Permissions licenses must have a description"
        super(SpecialPermissionsLicense, self).__init__(copyright_holder=copyright_holder, description=description)
