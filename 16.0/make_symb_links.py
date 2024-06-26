#!/usr/bin/env python

import configparser
import os, sys
import ast
import subprocess

import pip
import pkg_resources
from pkg_resources import DistributionNotFound, VersionConflict

def should_install_requirement(requirement):
    should_install = False
    try:
        pkg_resources.require(requirement)
    except (DistributionNotFound, VersionConflict):
        should_install = True
    return should_install


def install_packages(requirement_list, odoo_addons=False):
    try:
        requirements = [
            requirement
            for requirement in requirement_list
            if should_install_requirement(requirement)
        ]
        if len(requirements) > 0:
            if odoo_addons:
                pip.main(['install', '--break-system-packages', '--target', '/mnt/extra-addons', *requirements])
            else:
                pip.main(['install', '--break-system-packages', *requirements])
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
            pip.main(['install', '--break-system-packages', '--ignore-installed', '-r', os.path.join(file_seek, "requirements.txt")])
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


if __name__ == '__main__':
    addons = []
    source_dir = '/opt/odoo/odoo-16.0'
    target_dir = '/var/lib/odoo/.local/share/Odoo/addons'
    conf = sys.argv[1] or "/etc/odoo/odoo.conf"

    config = configparser.ConfigParser()
    config.read(conf, "utf-8")

    if 'symlinks' in config.sections():
        for key, value in config['symlinks'].items():
            if key == 'source_dir':
                source_dir = value
            if key == 'target_dir':
                target_dir = value
            if key == 'priority':
                PRIORITY += value.split(',')
            if key == 'use_oca':
                subprocess.call([sys.executable, '-m', 'pipx', 'install', 'oca-maintainers-tools@git+https://github.com/OCA/maintainer-tools.git'])
                os.chdir("/opt/odoo/odoo-16.0")
                subprocess.call([sys.executable, 'oca-clone-everything --target-branch', '16.0'])
            if key == 'install_addons':
                install_packages(value.split(','))

    links, dependencies = check_dir(source_dir)
    addons += list(dependencies)

    for link in links:
        source = os.path.join(link[0], link[1])
        target = os.path.join(target_dir, link[1])
        if link[1] not in addons:
            continue
        try:
            os.symlink(source, target)
        except FileExistsError:
            print('Duplicate: {}'.format('/'.join(link)))
