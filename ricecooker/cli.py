import argparse
import os
import re
import subprocess
import sys
import uuid

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.ricecooker')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.yaml')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, 'templates')

import ricecooker
import ricecooker.config as config

from jinja2 import Template
import yaml

props = ['token', 'tempdir']
jiro_config = {}
if os.path.exists(CONFIG_FILE):
    jiro_config = yaml.full_load(open(CONFIG_FILE))


def save_config():
    global jiro_config
    os.makedirs(CONFIG_DIR, exist_ok=True)
    yaml.dump(jiro_config, open(CONFIG_FILE, 'w'))


def get_chef_script():
    if os.path.exists('chef.py'):
        return 'chef.py'

    return 'sushichef.py'


def prompt_for_token(remote_name):
    global jiro_config
    print("remote_name = {}".format(remote_name))
    remote = jiro_config['remotes'][remote_name]
    result = input("Please enter an authentication token for server {} ({}): ".format(remote_name, remote['url']))
    remote['token'] = result
    save_config()

    return result


def run_ricecooker(cmd, remote_name=None, extra_args=None):
    """
    Runs ricecooker. Should be run from a directory containing sushichef.py or chef.py.
    :param args: Object with passed parameters and default values.
    :return:
    """
    global jiro_config

    cmd_args = [
        sys.executable,
        get_chef_script(),
        cmd
    ]

    cmd_args.extend(extra_args)

    env = os.environ.copy()

    if 'tempdir' in jiro_config:
        env['TMPDIR'] = jiro_config['tempdir'].format(CHEFDIR=os.getcwd())
        print("TMPDIR = {}".format(env['TMPDIR']))

    token = None

    if remote_name:
        if remote_name in jiro_config['remotes']:
            remote = jiro_config['remotes'][remote_name]
            env['STUDIO_URL'] = remote['url']
            if 'token' in remote and remote['token']:
                token = remote['token']
            else:
                token = prompt_for_token(remote_name)
            cmd_args.extend(['--token', token])
        else:
            print("ERROR: No remote with name {} found. To see available remotes, run: jiro remote list")
            sys.exit(1)

    print("Running {}".format(cmd_args))
    return subprocess.call(cmd_args, env=env)


def add_default_remote():
    global jiro_config
    if not 'remotes' in jiro_config:
        jiro_config['remotes'] = {'default': {'url': config.DEFAULT_DOMAIN}}

    # Note: we won't prompt for token until trying to upload to remote.
    save_config()


def add_remote(args, remainder):
    """
    Create a named alias for a remote server to upload to. If none are specified, will use the default server.
    :param args: Object containing .name and .url arguments.
    :return:
    """

    global jiro_config
    jiro_config['remotes'][args.name] = {
        'url': args.url,
        'token': args.token
    }
    save_config()


def list_remotes(args, remainder):
    """
    Create a named alias for a remote server to upload to. If none are specified, will use the default server.
    :param args: Object containing .name and .url arguments.
    :return:
    """

    global jiro_config
    for remote in jiro_config['remotes']:
        print("{}: {}".format(remote, jiro_config['remotes'][remote]['url']))


def set(args, remainder):
    """
    Sets a key / value pair in the config file.
    :param args: Object that contains .name and .value properties
    :return:
    """
    global jiro_config
    jiro_config[args.name] = args.value
    save_config()


def new_chef(args, remainder):

    name = args.name
    repo_name = "sushi-chef-{}".format(name.lower().replace(" ", "-"))

    # strip out non-alphanumeric charactesr from class name
    chef_name = re.sub('[^A-Za-z0-9]+', '', name.title())

    arg_dict = {
        'channel_id': uuid.uuid4().hex,
        'channel_name': name,
        'chef_name': chef_name
    }

    cwd = os.getcwd()
    repo_dir = os.path.join(cwd, repo_name)

    # If we've already created teh repo dir and are in it, then don't create a subdir with the same name.
    if repo_name in cwd:
        repo_dir = cwd

    os.makedirs(repo_dir, exist_ok=True)

    os.chdir(repo_dir)
    assets_dir = os.path.join(repo_dir, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    chef_filename = os.path.join(repo_dir, 'sushichef.py')
    if not os.path.exists(chef_filename):
        template = Template(open(os.path.join(TEMPLATE_DIR, 'sushichef.py')).read())
        output = template.render(**arg_dict)
        f = open(chef_filename, 'w')
        f.write(output)
        f.close()

    reqs_filename = os.path.join(repo_dir, 'requirements.txt')
    if not os.path.exists(reqs_filename):
        f = open(reqs_filename, 'w')
        f.write("ricecooker>={}".format(ricecooker.__version__))
        f.close()


def setup_env(args, remainder):
    cwd = os.getcwd()
    venv_dir = os.path.join(cwd, '.venv')
    if not os.path.exists(venv_dir):
        subprocess.call(['virtualenv', venv_dir])

    requirements = os.path.join(cwd, 'requirements.txt')
    assert os.path.exists(requirements), "No requirements.txt file found, cannot set up Python environment."
    subprocess.call(['pip', 'install', '-r', 'requirements.txt'])


def fetch(args, remainder):
    return run_ricecooker('fetch', extra_args=remainder)


def prepare(args, remainder):
    return run_ricecooker('dryrun', extra_args=remainder)


def serve(args, remainder):
    return run_ricecooker('uploadchannel', args.destination, extra_args=remainder)


def main():
    # ensure we always have the default remote set.
    add_default_remote()

    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(title='commands', help='Commands to operate on ricecooker projects')

    set_cmd = commands.add_parser('set')
    set_cmd.add_argument('name', nargs='?', help='Property to set. Choices are: %r' % (props,))
    set_cmd.add_argument('value', nargs='?', help='Value as string to set property to.')
    set_cmd.set_defaults(func=set)

    remote_cmd = commands.add_parser('remote')
    remote_cmds = remote_cmd.add_subparsers(title='remotes', description='Commands related to remote server management.')

    add_cmd = remote_cmds.add_parser('add')
    add_cmd.add_argument('name', nargs='?', help='Name of upload server.')
    add_cmd.add_argument('url', nargs='?', help='URL of server to upload to.')
    add_cmd.add_argument('token', nargs='?', help='User authentication token for server.')
    add_cmd.set_defaults(func=add_remote)

    list_cmd = remote_cmds.add_parser('list')
    list_cmd.set_defaults(func=list_remotes)

    setup_cmd = commands.add_parser('setup')
    setup_cmd.set_defaults(func=setup_env)

    new_cmd = commands.add_parser('new')
    new_cmd.add_argument('name', nargs='?', help='Name of new chef')
    new_cmd.set_defaults(func=new_chef)

    fetch_cmd = commands.add_parser('fetch')
    fetch_cmd.set_defaults(func=fetch)

    prepare_cmd = commands.add_parser('prepare')
    prepare_cmd.set_defaults(func=prepare)

    serve_cmd = commands.add_parser('serve')
    serve_cmd.add_argument('destination', nargs='?', default="default", help='Name of remote server to upload to.')
    serve_cmd.set_defaults(func=serve)

    # just pass down the remaining args to the command.
    args, unknown = parser.parse_known_args()
    sys.exit(args.func(args, unknown))
