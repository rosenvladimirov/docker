#!/usr/bin/env python3

import argparse
import ast
import configparser
import glob
import logging
import os
import subprocess
import sys
from importlib.metadata import distribution

BRANCH = os.environ.get('ODOO_BRANCH', '17.0')
UNINSTALL = []


def recursive_file_permissions(path, uid=-1, gid=-1):
    print(f"Change owner: {path} {uid}:{gid}")

    for item in glob.glob(path + '/*', recursive=True):
        print(f"Start to change owner for {item}")
        try:
            os.chown(item, uid, gid)
            print(f"Changed owner for {item}")
        except Exception as e:
            print('Path permissions on {0} not updated due to error {1}.'.format(item, e))

        if os.path.isdir(item):
            recursive_file_permissions(os.path.join(path, item), uid, gid)


def recursive_git_pull(path):
    def git_pull(git_path):
        os.chdir(git_path)
        subprocess.call(['git', 'fetch'])
        subprocess.call(['git', 'pull'])

    for item in glob.glob(path + '/*'):
        if os.path.isdir(os.path.join(item, '.git')):
            git_pull(item)
            continue
        if os.path.isdir(item):
            recursive_git_pull(os.path.join(path, item))


def get_module_logger(mod_name):
    """
    To use this, do logger = get_module_logger(__name__)
    """
    logger = logging.getLogger(mod_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname) ? [%(filename)s:%(lineno)d]: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def should_install_requirement(requirement, skip_test=False):
    should_install = False
    if not skip_test and requirement in UNINSTALL:
        return should_install
    try:
        distribution(requirement)
    except ImportError:
        should_install = True
    return should_install


def should_uninstall_requirement(requirement):
    should_install = True
    try:
        distribution(requirement)
    except ImportError:
        should_install = False
    return should_install


def install_packages(requirement_list, target_destinations, requirements=False):
    try:
        if requirements:
            uninstall_requirements = False
            print(f"Install python requirements {requirements}...")
            if UNINSTALL:
                # without_uninstall = f'grep -ivE "{"|".join(UNINSTALL)}" {requirements}'
                # uninstall_requirements = tempfile.NamedTemporaryFile(delete=False)
                uninstall_requirements = f'/tmp/{os.path.split(requirements)[-1]}'
                with open(uninstall_requirements, 'w') as f:
                    subprocess.call([
                        'grep', '-ivE', f'{"|".join(UNINSTALL)}', requirements], stdout=f)
                if os.path.isfile(uninstall_requirements) and os.path.getsize(uninstall_requirements) > 0:
                    requirements = uninstall_requirements
            subprocess.call(
                [sys.executable, '-m', 'pip', 'install', '--upgrade',
                 '--target', target_destinations, '-r', requirements])
            if uninstall_requirements:
                os.unlink(uninstall_requirements)

        else:
            requirements = [
                requirement
                for requirement in requirement_list
                if should_install_requirement(requirement)
            ]
            if len(requirements) > 0:
                print(f"Install python package {requirements}...")
                for package in requirements:
                    subprocess.call(
                        [sys.executable, '-m', 'pip', 'install', '--upgrade',
                         '--target', target_destinations, package])
            else:
                print("Requirements already satisfied.")
    except Exception as e:
        print(e)


def uninstall_packages(requirement_list):
    requirements = [
        requirement
        for requirement in requirement_list
        if should_uninstall_requirement(requirement)
    ]
    if len(requirements) > 0:
        for requirement in requirements:
            print(f"Uninstall python package {requirement}...")
            subprocess.call(
                [sys.executable, '-m', 'pip', 'uninstall', '--yes', f'{requirement}'])
    else:
        print("Requirements already satisfied.")


PRIORITY = []
IGNORE = ['.git', 'setup', '.gitignore', '.idea']
ADDONS = []


def check_dir(dir_addons, links_seek=None, depends=None, main=None, install_requirements=None):
    if depends is None:
        depends = set()
    if links_seek is None:
        links_seek = []
    if main is None:
        main = []

    for file_seek in sorted(glob.glob(dir_addons + '/*', recursive=True), key=lambda t: t in set(PRIORITY), reverse=True):
        clear_name = os.path.split(file_seek)[-1]
        manifest_file = os.path.join(file_seek, '__manifest__.py')
        requirements_file = os.path.join(file_seek, "requirements.txt")

        if os.path.exists(requirements_file) and install_requirements:
            install_packages([],
                             '/opt/python3',
                             os.path.join(dir_addons, file_seek, "requirements.txt"))

        if os.path.exists(manifest_file) and clear_name not in set(IGNORE) and os.path.islink(file_seek):
            links_seek.append((dir_addons, file_seek))
            with open(manifest_file) as manifest:
                data = ast.literal_eval(manifest.read())
            if data.get('depends'):
                for line in data['depends']:
                    if line not in main:
                        depends.update([line])
            if data.get('external_dependencies') and data['external_dependencies'].get('python'):
                install_packages(data['external_dependencies']['python'], '/opt/python3')
        else:
            links_seek, depends = check_dir(file_seek, links_seek, depends, main, install_requirements)
    return links_seek, depends


def install_oca_addons(oca_folder):
    os.chdir(oca_folder)
    print(f"Installing OCA addons... on {oca_folder}")
    subprocess.call(['oca-clone-everything', '--target-branch', f"{BRANCH}"])


def install_ee_addons(ee_folder, user, token):
    os.chdir(ee_folder)
    print(f"Install ee modules... on {user}:{token} {ee_folder}")
    subprocess.call(['git', 'clone', '--branch', f"{BRANCH}", f'https://oauth2:{token}@github.com:odoo/enterprise.git'])


def github_credentials(user, password, email):
    if user and password and email:
        if os.path.isfile('/usr/local/bin/github_credentials.sh'):
            print(f"Create credentials for {user}")
            # subprocess.call(['github_credentials.sh', '-u', user, '-e', email])
            subprocess.call(['github_credentials.sh', '-u', user, '-p', password, '-t', password, '-e', email])


def oca_credentials(user, password, odoo_username, odoo_password, app_username, app_password, oca_folder, update):
    os.chdir(oca_folder)
    config_oca = configparser.ConfigParser()
    if os.path.exists(f"{oca_folder}/oca.cfg"):
        config_oca.read(f"{oca_folder}/oca.cfg")

    update = update or not os.path.exists(f"{oca_folder}/oca.cfg")
    if update:
        if not config_oca.has_section('GitHub'):
            config_oca.add_section('GitHub')

        config_oca.set('GitHub', 'username', user or '')
        config_oca.set('GitHub', 'token', password or '')

        if not config_oca.has_section('odoo'):
            config_oca.add_section('odoo')

        config_oca.set('odoo', 'username', odoo_username or '')
        config_oca.set('odoo', 'password', odoo_password or '')

        if not config_oca.has_section('apps.odoo.com'):
            config_oca.add_section('apps.odoo.com')

        config_oca.set('apps.odoo.com', 'username', app_username or '')
        config_oca.set('apps.odoo.com', 'password', app_password or '')
        config_oca.set('apps.odoo.com', 'chromedriver_path', '/usr/lib/chromium-browser/chromedriver')
        with open(f"{oca_dir}/oca.cfg", 'w') as configfile:
            config_oca.write(configfile)


def get_config_print(config_file):
    res = []
    for section_line in config_file.sections():
        res.append(f"[{section_line}]")
        for items_key, items_val in config_file[section_line].items():
            res.append(f"{items_key} = {items_val}")
    return res


if __name__ == '__main__':
    config = force_update = False
    user_name = user_email = odoo_user_name = odoo_user_password = \
        app_user_name = app_user_password = token = use_oca = use_ee = python_package = use_requirements = False
    addons = []

    arg_parser = argparse.ArgumentParser(description='Installing odoo modules.')
    arg_parser.add_argument('conf',
                            metavar='addons.conf',
                            help='Configuration file')
    arg_parser.add_argument('-a', '--odoo-addons-oca',
                            dest='odoo_addons_oca',
                            help='Odoo oca addons installation')
    arg_parser.add_argument('-r', '--odoo-addons',
                            dest='odoo_addons',
                            help='Odoo addons installation')
    arg_parser.add_argument('-s', '--source-dir',
                            metavar='[full path]',
                            dest='source_dir',
                            help='Source directory for addons. Example: /opt/odoo/odoo-16.0')
    arg_parser.add_argument('-t', '--target-dir',
                            metavar='[full path]',
                            dest='target_dir',
                            help='Target directory for addons. Example: /var/lib/odoo/.local/share/Odoo/addons')
    arg_parser.add_argument('--addons-oca',
                            action='store_true',
                            dest='use_oca',
                            help='install all oca addons',
                            default=False)
    arg_parser.add_argument('--force-update',
                            action='store_true',
                            dest='force_update',
                            help='Force update config files and permissions',
                            default=False)
    arg_parser.add_argument('--addons-ее',
                            action='store_true',
                            dest='use_ee',
                            help='install all odoo enterprise addons',
                            default=False)
    arg_parser.add_argument('-u', '--uid',
                            dest='odoo_uid',
                            help='Odoo owner UID', )
    arg_parser.add_argument('-g', '--gid',
                            dest='odoo_gid',
                            help='Odoo owner GID', )

    args = arg_parser.parse_args()

    opt_dir = '/opt/odoo'
    source_dir = f'{opt_dir}/odoo-{BRANCH}'
    odoo_dir = '/var/lib/odoo'
    target_dir = f'{odoo_dir}/.local/share/Odoo/addons/{BRANCH}'
    oca_dir = f'{opt_dir}/odoo-{BRANCH}/oca'
    rv_dir = f'{opt_dir}/odoo-{BRANCH}/rv'
    ee_dir = f'{opt_dir}/odoo-{BRANCH}/ee'
    folders = [target_dir, oca_dir, rv_dir, ee_dir]

    supervisor = f'{opt_dir}/odoo-{BRANCH}/supervisor.txt'
    init = not os.path.isfile(supervisor)

    odoo_uid = args.odoo_uid or 100
    odoo_gid = args.odoo_gid or 100

    # sections = ['global', 'symlinks', 'github', 'odoo', 'apps.odoo.com', 'owner', 'addons']

    if args.conf and os.path.isfile(args.conf):
        config = configparser.ConfigParser()
        config.read(args.conf, "utf-8")

    if args.source_dir:
        source_dir = args.source_dir

    if args.target_dir:
        target_dir = args.target_dir

    if config:
        for section in config.sections():
            for key, value in config[section].items():
                if section == 'global':
                    if key == 'force_update':
                        force_update = config.getboolean(section, key)

                    if key == 'use_requirements':
                        use_requirements = config.getboolean(section, key)

                if section == 'symlinks':
                    if key == 'source_dir':
                        source_dir = value
                    if key == 'target_dir':
                        target_dir = value
                    if key == 'priority':
                        PRIORITY += value.split(',')

                if section == 'github':
                    if key == 'username':
                        user_name = value
                    if key == 'email':
                        user_email = value
                    if key == 'password':
                        token = value

                if section == 'odoo':
                    if key == 'username':
                        odoo_user_name = value
                    if key == 'password':
                        odoo_user_password = value

                if section == 'apps.odoo.com':
                    if key == 'username':
                        app_user_name = value
                    if key == 'password':
                        app_user_password = value

                if section == 'owner':
                    if key == 'uid':
                        odoo_uid = config.getint(section, key)
                    if key == 'gid':
                        odoo_gid = config.getint(section, key)

                if section == 'addons':
                    if key == 'use_oca':
                        use_oca = config.getboolean(section, key)
                    if key == 'odoo_addons_oca':
                        odoo_addons_oca = value
                    if key == 'use_ee':
                        use_ee = config.getboolean(section, key)

                if section == 'uninstall':
                    if key == 'python_package':
                        python_package = value

    for folder in folders:
        if not os.path.isdir(folder):
            os.makedirs(folder)

    if not os.path.exists(supervisor) or force_update:
        subprocess.call(['chown', '--recursive', f'{odoo_uid}:{odoo_gid}', odoo_dir])
        github_credentials(user_name, token, user_email)
        oca_credentials(user_name, token, odoo_user_name, odoo_user_password, app_user_name, app_user_password, oca_dir,
                        force_update)
        with open(supervisor, "w") as file:
            file.writelines([
                f"Force update: {force_update}\n",
                f"chown {odoo_uid}:{odoo_gid} {odoo_dir}\n",
                f"Write github credentials: {user_name}:{token}:{user_email}\n",
                f"Write oca credentials: {user_name}, {token}, {odoo_user_name}, {odoo_user_password}, {app_user_name}, {app_user_password}\n",
                f"Configurations: {args.conf}\n",
                config and "\n".join(get_config_print(config))
            ])

    if python_package:
        UNINSTALL = python_package.replace(" ", "").split(',')
        if UNINSTALL:
            uninstall_packages(UNINSTALL)

    if init and (args.use_oca or use_oca):
        install_oca_addons(oca_dir)
    elif force_update and not init and (args.use_oca or use_oca):
        recursive_git_pull(oca_dir)

    if init and (args.use_ee or use_ee):
        install_ee_addons(ee_dir, user_name, token)
    elif force_update and not init and (args.use_ee or use_ee):
        recursive_git_pull(ee_dir)

    if args.odoo_addons_oca:
        install_packages(args.odoo_addons_oca.split(','), '/mnt/extra-addons')

    links, dependencies = check_dir(source_dir, install_requirements=use_requirements)
    addons += list(dependencies)

    for link in links:
        source = os.path.join(link[0], link[1])
        target = os.path.join(target_dir, link[1])
        if link[1] not in addons:
            continue
        try:
            os.symlink(source, target)
            print(f'Symbolic link: {source} -> {target}')
        except FileExistsError:
            print(f'Duplicate: {source} to {target}')

    if os.path.isfile(os.path.join('/etc', 'odoo', "requirements.txt")):
        install_packages([], '/opt/python3', os.path.join('/etc', 'odoo', "requirements.txt"))

    if force_update or init:
        print(f"Force updating owner:...")
        recursive_file_permissions(odoo_dir, odoo_uid, odoo_gid)

    print(f"""Finish:\n
    Starting parameters:\n
    Odoo folder: {odoo_dir}\n
    Force: {force_update}\n
    Use requirements: {use_requirements}\n
    Source {source_dir} to {target_dir}\n
    Owner: {odoo_uid}:{odoo_gid}""")
