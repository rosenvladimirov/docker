#!/usr/bin/env python3

import configparser
import os, sys
import ast
import subprocess
import argparse
import pkg_resources
import logging

BRANCH = os.environ.get('ODOO_BRANCH', '17.0')

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


def should_install_requirement(requirement):
    should_install = False
    try:
        pkg_resources.require(requirement)
    except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
        should_install = True
    return should_install


def install_packages(requirement_list):
    try:
        requirements = [
            requirement
            for requirement in requirement_list
            if should_install_requirement(requirement)
        ]
        if len(requirements) > 0:
            subprocess.call(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', '/mnt/extra-addons', *requirements])
        else:
            print("Requirements already satisfied.")
    except Exception as e:
        print(e)


PRIORITY = []
IGNORE = ['.git', 'setup', '.gitignore', '.idea']
ADDONS = []


def check_dir(dir_addons, links_seek=None, depends=None, main=None):
    if depends is None:
        depends = set()
    if links_seek is None:
        links_seek = []
    if main is None:
        main = []
    dir_list = os.listdir(dir_addons)
    dir_list.sort(key=lambda t: t in set(PRIORITY), reverse=True)
    for file_seek in dir_list:
        if os.path.isfile(os.path.join(file_seek, "requirements.txt")):
            subprocess.call([sys.executable, '-m', 'pip', 'install', '--ignore-installed', '-r',
                             os.path.join(file_seek, "requirements.txt")])
        check_file_directory = os.path.join(dir_addons, file_seek)
        if os.path.isdir(check_file_directory) and not (file_seek in set(IGNORE)) and not os.path.islink(
                check_file_directory):
            manifest_path = os.path.join(check_file_directory, '__manifest__.py')
            if os.path.exists(manifest_path):
                links_seek.append((dir_addons, file_seek))
                with open(manifest_path) as manifest:
                    data = ast.literal_eval(manifest.read())
                if data.get('depends'):
                    for line in data['depends']:
                        if line not in main:
                            depends.update([line])
                if data.get('external_dependencies') and data['external_dependencies'].get('python'):
                    install_packages(data['external_dependencies']['python'])
            else:
                links_seek, depends = check_dir(check_file_directory, links_seek, depends, main)
    return links_seek, depends


def install_oca_addons(oca_folder):
    os.chdir(oca_folder)
    print(f"Installing OCA addons... on {oca_folder}")
    subprocess.call(['oca-clone-everything', '--target-branch', f"{BRANCH}"])


def install_ee_addons(ee_folder):
    os.chdir(ee_folder)
    print(f"Install ee modules... on {ee_folder}")
    subprocess.call(['git', 'clone', '--branch', f"{BRANCH}", 'git@github.com:odoo/enterprise.git'])


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
    user_name = user_email = odoo_user_name = odoo_user_password = app_user_name = app_user_password = token = use_oca = use_ee = False
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
    target_dir = f'{odoo_dir}/.local/share/Odoo/addons'
    oca_dir = f'{opt_dir}/odoo-{BRANCH}/oca'
    rv_dir = f'{opt_dir}/odoo-{BRANCH}/rv'
    ee_dir = f'{opt_dir}/odoo-{BRANCH}/ee'
    folders = [target_dir, oca_dir, rv_dir, ee_dir]

    supervisor = f'{opt_dir}/odoo-{BRANCH}/supervisor.txt'
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
                    if key in 'force_update':
                        force_update = value

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
                        user_uid = value
                    if key == 'gid':
                        user_gid = value

                if section == 'addons':
                    if key == 'use_oca':
                        use_oca = value
                    if key == 'odoo_addons_oca':
                        odoo_addons_oca = value
                    if key == 'use_ee':
                        use_ee = value

    for folder in folders:
        if not os.path.isdir(folder):
            os.makedirs(folder)

    if not os.path.exists(supervisor) or force_update:
        os.chown(odoo_dir, uid=odoo_uid, gid=odoo_gid)
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

    if args.use_oca or use_oca:
        install_oca_addons(oca_dir)

    if args.odoo_addons_oca:
        install_packages(args.odoo_addons_oca.split(','))

    if args.use_ee or use_ee:
        install_ee_addons(ee_dir)

    links, dependencies = check_dir(source_dir)
    addons += list(dependencies)

    for link in links:
        source = os.path.join(link[0], link[1])
        target = os.path.join(target_dir, link[1])
        if link[1] not in addons:
            continue
        try:
            os.symlink(source, target)
            print(f'Symbolic link: {source} -> {target}')
            # get_module_logger(__name__).info('Source %s to %s', source, target)
        except FileExistsError:
            print(f'Duplicate: {source}')
            # get_module_logger(__name__).info('Duplicate: %s', source)
