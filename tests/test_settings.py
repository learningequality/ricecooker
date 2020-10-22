import sys

from mock import patch

from ricecooker import chefs


settings = {
    'generate-missing-thumbnails': True,
    'compress-videos': True
}


def test_settings_unset_default():
    chef = chefs.SushiChef()

    for setting in settings:
        assert chef.get_setting(setting) is None
        assert chef.get_setting(setting, default=False) is False


def test_settings():
    chef = chefs.SushiChef()

    for setting in settings:
        value = settings[setting]
        chef.SETTINGS[setting] = value
        assert chef.get_setting(setting) == value
        assert chef.get_setting(setting, default=None) == value


def test_cli_args_override_settings():
    """
    For settings that can be controlled via the command line, ensure that the command line setting
    takes precedence over the default setting.
    """

    test_argv = ['sushichef.py', '--compress', '--thumbnails', '--token', '12345']

    with patch.object(sys, 'argv', test_argv):
        chef = chefs.SushiChef()
        chef.SETTINGS['generate-missing-thumbnails'] = False
        chef.SETTINGS['compress-videos'] = False

        assert chef.get_setting('generate-missing-thumbnails') == False
        assert chef.get_setting('compress-videos') == False

        chef.parse_args_and_options()
        assert chef.get_setting('generate-missing-thumbnails') == True
        assert chef.get_setting('compress-videos') == True

    test_argv = ['sushichef.py', '--compress', '--thumbnails', '--token', '12345']

    with patch.object(sys, 'argv', test_argv):
        chef = chefs.SushiChef()

        assert len(chef.SETTINGS) == 0

        assert chef.get_setting('generate-missing-thumbnails') == None
        assert chef.get_setting('compress-videos') == None

        chef.parse_args_and_options()
        assert chef.get_setting('generate-missing-thumbnails') == True
        assert chef.get_setting('compress-videos') == True

    # now test without setting the flags
    test_argv = ['sushichef.py', '--token', '12345']

    with patch.object(sys, 'argv', test_argv):
        chef = chefs.SushiChef()
        chef.SETTINGS['generate-missing-thumbnails'] = False
        chef.SETTINGS['compress-videos'] = False

        assert chef.get_setting('generate-missing-thumbnails') == False
        assert chef.get_setting('compress-videos') == False

        chef.parse_args_and_options()
        assert chef.get_setting('generate-missing-thumbnails') == False
        assert chef.get_setting('compress-videos') == False
