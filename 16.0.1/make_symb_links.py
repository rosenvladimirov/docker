#!/usr/bin/env python3

import configparser
import os, sys
import ast
import subprocess
import argparse
import pkg_resources
import logging


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
            subprocess.call([sys.executable, '-m', 'pip', 'install', '--no-dependencies', '--upgrade', '--target', '/mnt/extra-addons', *requirements])
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
            subprocess.call([sys.executable, '-m', 'pip', 'install', '--ignore-installed', '-r', os.path.join(file_seek, "requirements.txt")])
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


def install_oca_addons():
    subprocess.call([sys.executable, '-m', 'pipx', 'install',
                     'oca-maintainers-tools@git+https://github.com/OCA/maintainer-tools.git'])
    os.chdir("/opt/odoo/odoo-16.0/oca")
    subprocess.call([sys.executable, '/usr/local/bin/oca-clone-everything --target-branch', '16.0'])


def install_ее_addons():
    os.chdir("/opt/odoo/odoo-16.0/ee")
    subprocess.call(['git', 'clone', '--branch', '16.0', 'git@github.com:odoo/enterprise.git'])


if __name__ == '__main__':
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
    arg_parser.add_argument('--addons-ее',
                            action='store_true',
                            dest='use_ее',
                            help='install all odoo enterprise addons',
                            default=False)

    args = arg_parser.parse_args()

    config = False
    addons = []
    source_dir = '/opt/odoo/odoo-16.0'
    target_dir = '/var/lib/odoo/.local/share/Odoo/addons'
    user_name = user_email = token = False

    if args.conf:
        config = configparser.ConfigParser()
        config.read(args.conf, "utf-8")

    if args.source_dir:
        source_dir = args.source_dir

    if args.target_dir:
        target_dir = args.target_dir

    if config and 'symlinks' in config.sections():
        for key, value in config['symlinks'].items():
            if key == 'source_dir':
                source_dir = value
            if key == 'target_dir':
                target_dir = value
            if key == 'priority':
                PRIORITY += value.split(',')
    if config and 'github' in config.sections():
            if key == 'username':
                user_name = value
            if key == 'email':
                user_email = value
            if key == 'password':
                token = value

    if user_name and token and user_email:
        subprocess.call(['git', 'config', '--global', f'user.name "{user_name}"'])
        subprocess.call(['git', 'config', '--global', f'user.password "{token}"'])
        subprocess.call(['git', 'config', '--global', f'user.email "{user_email}"'])
        subprocess.call(['git', 'config', '--global', 'credential.helper "cache --timeout=3600"'])
        subprocess.call(['git', 'config', '--global',  f'url."https://git:{token}@github.com/".insteadOf "git@github.com:"'])

    if args.use_oca:
        install_oca_addons()
    if args.odoo_addons_oca:
        install_packages(args.odoo_addons_oca.split(','))

    links, dependencies = check_dir(source_dir)
    addons += list(dependencies)

    for link in links:
        source = os.path.join(link[0], link[1])
        target = os.path.join(target_dir, link[1])
        if link[1] not in addons:
            continue
        try:
            os.symlink(source, target)
            get_module_logger(__name__).info(f'Source: {source} to {target}')
        except FileExistsError:
            get_module_logger(__name__).info(f'Duplicate: {"/".join(link)}')
