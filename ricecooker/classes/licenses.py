# License models

from ..exceptions import UnknownLicenseError
from le_utils.constants import licenses

def get_license(license_id, copyright_holder=None):
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
    else:
        raise UnknownLicenseError("{} is not a valid license id. (Valid license are {})".format(license_id, [l[0] for l in licenses.choices]))


class License(object):
    license_id = None # (str): content's license based on le_utils.constants.licenses
    copyright_holder = None # (str): name of person or organization who owns license (optional)

    def __init__(self, copyright_holder=None):
        self.copyright_holder = copyright_holder or ""

    def get_id(self):
        return self.license_id

    def validate(self):
        assert isinstance(copyright_holder, str), "Assertion Failed: Copyright holder must be a string"

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
    license_id = licenses.PUBLIC_DOMAIN
