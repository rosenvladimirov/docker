#!/usr/bin/env python3

import argparse
import ast
import configparser
import glob
import os
import subprocess
import sys
from importlib.metadata import distribution, PackageNotFoundError
from typing import Iterable, List, Optional, Sequence, Tuple, Dict

# Constants
BRANCH = os.environ.get('ODOO_BRANCH', '18.0')
UNINSTALL: List[str] = []

DEFAULT_OPT_DIR = '/opt/odoo'
DEFAULT_ODOO_DIR = '/var/lib/odoo'
DEFAULT_PY_TARGET = '/opt/python3'
DEFAULT_EXTRA_ADDONS = '/mnt/extra-addons'
GITHUB_CRED_SCRIPT = '/usr/local/bin/github_credentials.sh'

IGNORE = {'.git', 'setup', '.gitignore', '.idea'}

# Strict mode for init-container: fail fast
STRICT_MODE = False


def run_cmd(cmd: Sequence[str], cwd: Optional[str] = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def recursive_file_permissions(path: str, uid: int = -1, gid: int = -1) -> None:
    print(f"Change owner: {path} {uid}:{gid}")
    try:
        os.chown(path, uid, gid)
    except Exception as e:
        print(f'Path permissions on {path} not updated due to error {e}.')
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            item = os.path.join(root, name)
            try:
                os.chown(item, uid, gid)
            except Exception as e:
                print('Path permissions on {0} not updated due to error {1}.'.format(item, e))


def recursive_git_pull(path: str) -> None:
    def git_pull(git_path: str) -> None:
        run_cmd(['git', 'fetch'], cwd=git_path)
        run_cmd(['git', 'pull'], cwd=git_path)

    for item in glob.glob(os.path.join(path, '*')):
        if os.path.isdir(os.path.join(item, '.git')):
            git_pull(item)
            continue
        if os.path.isdir(item):
            recursive_git_pull(item)


def should_install_requirement(requirement: str, skip_test: bool = False) -> bool:
    if not skip_test and requirement in UNINSTALL:
        return False
    try:
        distribution(requirement)
        return False
    except PackageNotFoundError:
        return True


def should_uninstall_requirement(requirement: str) -> bool:
    try:
        distribution(requirement)
        return True
    except PackageNotFoundError:
        return False


def install_packages(requirement_list: Sequence[str], target_destinations: str, requirements: Optional[str] = None) -> None:
    try:
        if requirements:
            uninstall_requirements: Optional[str] = None
            print(f"Install python requirements {requirements}...")
            if UNINSTALL:
                uninstall_requirements = f'/tmp/{os.path.basename(requirements)}'
                with open(uninstall_requirements, 'w') as f:
                    subprocess.run(['grep', '-ivE', f'{"|".join(UNINSTALL)}', requirements], stdout=f, check=True)
                if os.path.isfile(uninstall_requirements) and os.path.getsize(uninstall_requirements) > 0:
                    requirements = uninstall_requirements
            run_cmd([sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', target_destinations, '-r', requirements])
            if uninstall_requirements:
                try:
                    os.unlink(uninstall_requirements)
                except OSError:
                    pass
        else:
            to_install = [pkg for pkg in requirement_list if should_install_requirement(pkg)]
            if to_install:
                print(f"Install python package {to_install}...")
                for package in to_install:
                    run_cmd([sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', target_destinations, package])
            else:
                print("Requirements already satisfied.")
    except Exception as e:
        if STRICT_MODE:
            raise
        print(e)


def uninstall_packages(requirement_list: Iterable[str]) -> None:
    to_remove = [requirement for requirement in requirement_list if should_uninstall_requirement(requirement)]
    if to_remove:
        for requirement in to_remove:
            print(f"Uninstall python package {requirement}...")
            try:
                run_cmd([sys.executable, '-m', 'pip', 'uninstall', '--yes', f'{requirement}'])
            except Exception as e:
                if STRICT_MODE:
                    raise
                print(e)
    else:
        print("Requirements already satisfied.")


def collect_links_and_deps(
    dir_addons: str,
    links_seek: Optional[List[Tuple[str, str]]] = None,
    depends: Optional[set] = None,
    main: Optional[List[str]] = None,
    install_requirements: Optional[bool] = None,
    priority: Optional[Sequence[str]] = None
) -> Tuple[List[Tuple[str, str]], set]:
    if depends is None:
        depends = set()
    if links_seek is None:
        links_seek = []
    if main is None:
        main = []
    priority_set = set(priority or ())

    for entry in sorted(glob.glob(os.path.join(dir_addons, '*')),
                        key=lambda t: os.path.basename(t) in priority_set,
                        reverse=True):
        name = os.path.basename(entry)
        manifest_file = os.path.join(entry, '__manifest__.py')
        requirements_file = os.path.join(entry, "requirements.txt")

        if os.path.exists(requirements_file) and install_requirements:
            print(f"Found {requirements_file}, starting install")
            install_packages([], DEFAULT_PY_TARGET, requirements_file)

        if os.path.exists(manifest_file) and name not in IGNORE and os.path.islink(entry):
            links_seek.append((dir_addons, entry))
            with open(manifest_file, 'r', encoding='utf-8') as manifest:
                data = ast.literal_eval(manifest.read())
            if data.get('depends'):
                for dep in data['depends']:
                    if dep not in main:
                        depends.add(dep)
            if data.get('external_dependencies') and data['external_dependencies'].get('python'):
                install_packages(data['external_dependencies']['python'], DEFAULT_PY_TARGET)
        elif os.path.isdir(entry):
            links_seek, depends = collect_links_and_deps(
                entry, links_seek, depends, main, install_requirements, priority=priority
            )
    return links_seek, depends


def install_oca_addons(oca_folder: str) -> None:
    print(f"Installing OCA addons... on {oca_folder}")
    run_cmd(['oca-clone-everything', '--target-branch', f"{BRANCH}"], cwd=oca_folder)


def install_ee_addons(ee_folder: str, user: str, token: str) -> None:
    masked = f"{user}:***"
    print(f"Install ee modules... on {masked} {ee_folder}")
    run_cmd(['git', 'clone', '--branch', f"{BRANCH}", f'https://oauth2:{token}@github.com/odoo/enterprise.git'], cwd=ee_folder)


def github_credentials(user: Optional[str], token: Optional[str], email: Optional[str]) -> None:
    if user and token and email and os.path.isfile(GITHUB_CRED_SCRIPT):
        print(f"Create credentials for {user}")
        run_cmd([GITHUB_CRED_SCRIPT, '-u', user, '-t', token, '-e', email])


def oca_credentials(
    user: Optional[str],
    password: Optional[str],
    odoo_username: Optional[str],
    odoo_password: Optional[str],
    app_username: Optional[str],
    app_password: Optional[str],
    oca_folder: str,
    update: bool
) -> None:
    config_oca = configparser.ConfigParser()
    cfg_path = os.path.join(oca_folder, 'oca.cfg')
    if os.path.exists(cfg_path):
        config_oca.read(cfg_path)

    update = update or not os.path.exists(cfg_path)
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
        with open(cfg_path, 'w') as configfile:
            config_oca.write(configfile)


def get_config_print(config_file: configparser.ConfigParser) -> List[str]:
    res: List[str] = []
    for section_line in config_file.sections():
        res.append(f"[{section_line}]")
        for items_key, items_val in config_file[section_line].items():
            res.append(f"{items_key} = {items_val}")
    return res


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Installing odoo modules.')
    parser.add_argument('conf', metavar='addons.conf', help='Configuration file')
    parser.add_argument('-a', '--odoo-addons-oca', dest='odoo_addons_oca', help='Odoo oca addons installation')
    parser.add_argument('-r', '--odoo-addons', dest='odoo_addons', help='Odoo addons installation')
    parser.add_argument('-s', '--source-dir', metavar='[full path]', dest='source_dir',
                        help='Source directory for addons. Example: /opt/odoo/odoo-18.0')
    parser.add_argument('-t', '--target-dir', metavar='[full path]', dest='target_dir',
                        help='Target directory for addons. Example: /var/lib/odoo/.local/share/Odoo/addons')
    parser.add_argument('--addons-oca', action='store_true', dest='use_oca', help='install all oca addons', default=False)
    parser.add_argument('--force-update', action='store_true', dest='force_update',
                        help='Force update config files and permissions', default=False)
    parser.add_argument('--addons-ее', action='store_true', dest='use_ee', help='install all odoo enterprise addons',
                        default=False)
    parser.add_argument('--init-container', action='store_true', dest='init_container',
                        help='Enable strict init-container mode (fail fast, force requirements & update).', default=False)
    parser.add_argument('-u', '--uid', dest='odoo_uid', help='Odoo owner UID')
    parser.add_argument('-g', '--gid', dest='odoo_gid', help='Odoo owner GID')
    return parser.parse_args()


def extract_settings_from_config(config: configparser.ConfigParser) -> Dict[str, object]:
    settings: Dict[str, object] = {
        'force_update': False,
        'use_requirements': False,
        'source_dir': None,
        'target_dir': None,
        'priority_list': [],
        'user_name': None,
        'user_email': None,
        'token': None,
        'odoo_user_name': None,
        'odoo_user_password': None,
        'app_user_name': None,
        'app_user_password': None,
        'odoo_uid': None,
        'odoo_gid': None,
        'use_oca': False,
        'use_ee': False,
        'odoo_addons_oca': None,
        'python_package': None,
    }
    for section in config.sections():
        for key, value in config[section].items():
            if section == 'global':
                if key == 'force_update':
                    settings['force_update'] = config.getboolean(section, key)
                if key == 'use_requirements':
                    settings['use_requirements'] = config.getboolean(section, key)
            elif section == 'symlinks':
                if key == 'source_dir':
                    settings['source_dir'] = value
                if key == 'target_dir':
                    settings['target_dir'] = value
                if key == 'priority':
                    settings['priority_list'] += [v for v in value.split(',') if v]
            elif section == 'github':
                if key == 'username':
                    settings['user_name'] = value
                if key == 'email':
                    settings['user_email'] = value
                if key == 'password':
                    settings['token'] = value
            elif section == 'odoo':
                if key == 'username':
                    settings['odoo_user_name'] = value
                if key == 'password':
                    settings['odoo_user_password'] = value
            elif section == 'apps.odoo.com':
                if key == 'username':
                    settings['app_user_name'] = value
                if key == 'password':
                    settings['app_user_password'] = value
            elif section == 'owner':
                if key == 'uid':
                    settings['odoo_uid'] = config.getint(section, key)
                if key == 'gid':
                    settings['odoo_gid'] = config.getint(section, key)
            elif section == 'addons':
                if key == 'use_oca':
                    settings['use_oca'] = config.getboolean(section, key)
                if key == 'odoo_addons_oca':
                    settings['odoo_addons_oca'] = value
                if key == 'use_ee':
                    settings['use_ee'] = config.getboolean(section, key)
            elif section == 'uninstall':
                if key == 'python_package':
                    settings['python_package'] = value
    return settings


def normalize_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v for v in (s.strip() for s in value.split(',')) if v]


def main() -> int:
    global STRICT_MODE

    args = parse_args()

    # Detect init mode via CLI or ENV
    env_init = os.getenv('ODOO_INIT_CONTAINER', '').strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    init_mode = bool(args.init_container or env_init)
    STRICT_MODE = init_mode

    opt_dir = DEFAULT_OPT_DIR
    source_dir = args.source_dir or f'{opt_dir}/odoo-{BRANCH}'
    odoo_dir = DEFAULT_ODOO_DIR
    target_dir = args.target_dir or f'{odoo_dir}/.local/share/Odoo/addons/{BRANCH}'
    oca_dir = f'{opt_dir}/odoo-{BRANCH}/oca'
    ee_dir = f'{opt_dir}/odoo-{BRANCH}/ee'
    folders = [target_dir, oca_dir, ee_dir]

    supervisor = f'{opt_dir}/odoo-{BRANCH}/supervisor.txt'
    init = not os.path.isfile(supervisor)

    odoo_uid = int(args.odoo_uid) if args.odoo_uid is not None else 100
    odoo_gid = int(args.odoo_gid) if args.odoo_gid is not None else 100

    config = configparser.ConfigParser()
    if args.conf and os.path.isfile(args.conf):
        config.read(args.conf, "utf-8")

    settings = extract_settings_from_config(config)

    # Defaults from config
    force_update = bool(settings['force_update'])
    use_requirements = bool(settings['use_requirements'])
    source_dir = settings['source_dir'] or source_dir
    target_dir = settings['target_dir'] or target_dir
    priority_list = list(settings['priority_list'])
    user_name = settings['user_name']
    user_email = settings['user_email']
    token = settings['token']
    odoo_user_name = settings['odoo_user_name']
    odoo_user_password = settings['odoo_user_password']
    app_user_name = settings['app_user_name']
    app_user_password = settings['app_user_password']
    if settings['odoo_uid'] is not None:
        odoo_uid = int(settings['odoo_uid'])
    if settings['odoo_gid'] is not None:
        odoo_gid = int(settings['odoo_gid'])
    use_oca = bool(settings['use_oca'])
    use_ee = bool(settings['use_ee'])
    odoo_addons_oca = settings['odoo_addons_oca']
    python_package = settings['python_package']

    # Init mode forces requirements and update to ensure full preparation
    if init_mode:
        use_requirements = True
        force_update = True

    # Create folders
    for folder in folders:
        os.makedirs(folder, exist_ok=True)

    try:
        if not os.path.exists(supervisor) or force_update:
            try:
                run_cmd(['chown', '--recursive', f'{odoo_uid}:{odoo_gid}', odoo_dir])
            except Exception as e:
                if STRICT_MODE:
                    raise
                print(f"chown failed: {e}")

            github_credentials(user_name, token, user_email)
            oca_credentials(user_name, token, odoo_user_name, odoo_user_password, app_user_name, app_user_password, oca_dir, force_update)

            lines: List[str] = [
                f"Force update: {force_update}\n",
                f"chown {odoo_uid}:{odoo_gid} {odoo_dir}\n",
                f"Write github credentials: {user_name}:{'***' if token else token}:{user_email}\n",
                f"Write oca credentials: {user_name}, {'***' if token else token}, {odoo_user_name}, {odoo_user_password}, {app_user_name}, {app_user_password}\n",
                f"Configurations: {args.conf}\n",
            ]
            lines.extend(get_config_print(config))
            lines.append("\n")
            with open(supervisor, "w") as file:
                file.writelines(lines)

        if python_package:
            UNINSTALL[:] = normalize_list(python_package)
            if UNINSTALL:
                uninstall_packages(UNINSTALL)

        # Prepare OCA/EE trees
        if init and (args.use_oca or use_oca):
            install_oca_addons(oca_dir)
        elif force_update and not init and (args.use_oca or use_oca):
            recursive_git_pull(oca_dir)

        if init and (args.use_ee or use_ee):
            if not token and STRICT_MODE:
                raise RuntimeError("Enterprise installation requested but GITHUB_TOKEN is missing.")
            install_ee_addons(ee_dir, user_name or '', token or '')
        elif force_update and not init and (args.use_ee or use_ee):
            recursive_git_pull(ee_dir)

        # Optional explicit addons lists (extra-addons)
        if args.odoo_addons_oca or odoo_addons_oca:
            install_packages(normalize_list(args.odoo_addons_oca or odoo_addons_oca), DEFAULT_EXTRA_ADDONS)
        if getattr(args, 'odoo_addons', None):
            install_packages(normalize_list(args.odoo_addons), DEFAULT_EXTRA_ADDONS)

        # Global requirements
        etc_requirements = os.path.join('/etc', 'odoo', "requirements.txt")
        if os.path.isfile(etc_requirements):
            install_packages([], DEFAULT_PY_TARGET, etc_requirements)

        # Scan source dir: install addon requirements and collect links
        links, dependencies = collect_links_and_deps(
            source_dir, install_requirements=use_requirements, priority=priority_list
        )
        addons: List[str] = list(dependencies)

        # Create symlinks for collected addons
        for dir_addons, entry in links:
            source = entry
            target = os.path.join(target_dir, os.path.basename(entry))
            if os.path.basename(entry) not in addons:
                continue
            try:
                if os.path.islink(target) or os.path.exists(target):
                    print(f'Duplicate: {source} to {target}')
                    continue
                os.symlink(source, target)
                print(f'Symbolic link: {source} -> {target}')
            except FileExistsError:
                print(f'Duplicate: {source} to {target}')

        if force_update or init:
            print("Force updating owner:...")
            recursive_file_permissions(odoo_dir, odoo_uid, odoo_gid)

        print(f"""Finish:\n
        Starting parameters:\n
        Odoo folder: {odoo_dir}\n
        Force: {force_update}\n
        Use requirements: {use_requirements}\n
        Source {source_dir} to {target_dir}\n
        Owner: {odoo_uid}:{odoo_gid}""")
        return 0
    except Exception as e:
        # In init mode: fail fast to let initContainer stop the Pod
        print(f"ERROR: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
