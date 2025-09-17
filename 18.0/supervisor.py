#!/usr/bin/env python3

import argparse
import ast
import configparser
import glob
import logging
import os
import subprocess
import sys
from importlib.metadata import distribution, PackageNotFoundError
from typing import Iterable, List, Optional, Sequence, Tuple, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    """Execute a command and log the result."""
    try:
        logger.info(f"Executing command: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=cwd, check=True)
        logger.info("Command executed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with return code {e.returncode}: {' '.join(cmd)}")
        raise


def recursive_file_permissions(path: str, uid: int = -1, gid: int = -1) -> None:
    """Recursively change file ownership."""
    if not os.path.exists(path):
        logger.warning(f"Path does not exist: {path}")
        return

    logger.info(f"Changing owner: {path} {uid}:{gid}")
    try:
        os.chown(path, uid, gid)
    except Exception as e:
        logger.error(f'Path permissions on {path} not updated due to error {e}.')

    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            item = os.path.join(root, name)
            try:
                os.chown(item, uid, gid)
            except Exception as e:
                logger.error(f'Path permissions on {item} not updated due to error {e}.')


def recursive_git_pull(path: str) -> None:
    """Recursively pull all git repositories in a directory."""
    if not os.path.exists(path):
        logger.warning(f"Git pull path does not exist: {path}")
        return

    def git_pull(git_path: str) -> None:
        logger.info(f"Git pull in: {git_path}")
        run_cmd(['git', 'fetch'], cwd=git_path)
        run_cmd(['git', 'pull'], cwd=git_path)

    for item in glob.glob(os.path.join(path, '*')):
        if os.path.isdir(os.path.join(item, '.git')):
            git_pull(item)
            continue
        if os.path.isdir(item):
            recursive_git_pull(item)


def should_install_requirement(requirement: str, skip_test: bool = False) -> bool:
    """Check if a Python package should be installed."""
    if not skip_test and requirement in UNINSTALL:
        logger.debug(f"Skipping {requirement} - in UNINSTALL list")
        return False
    try:
        dist = distribution(requirement)
        logger.debug(f"Package {requirement} already installed - version {dist.version}")
        return False
    except PackageNotFoundError:
        logger.debug(f"Package {requirement} not found - needs installation")
        return True


def should_uninstall_requirement(requirement: str) -> bool:
    """Check if a Python package should be uninstalled."""
    try:
        distribution(requirement)
        return True
    except PackageNotFoundError:
        return False


def install_packages(requirement_list: Sequence[str], target_destinations: str,
                     requirements: Optional[str] = None) -> None:
    """Install Python packages to a target directory."""
    if not requirement_list and not requirements:
        logger.debug("No packages to install")
        return

    try:
        if requirements:
            if not os.path.exists(requirements):
                logger.warning(f"Requirements file not found: {requirements}")
                return

            uninstall_requirements: Optional[str] = None
            logger.info(f"Installing python requirements from {requirements}...")

            if UNINSTALL:
                uninstall_requirements = f'/tmp/{os.path.basename(requirements)}'
                with open(uninstall_requirements, 'w') as f:
                    subprocess.run(['grep', '-ivE', f'{"|".join(UNINSTALL)}', requirements], stdout=f, check=True)
                if os.path.isfile(uninstall_requirements) and os.path.getsize(uninstall_requirements) > 0:
                    requirements = uninstall_requirements

            # Ensure target directory exists
            os.makedirs(target_destinations, exist_ok=True)
            run_cmd([sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', target_destinations, '-r',
                     requirements])

            if uninstall_requirements:
                try:
                    os.unlink(uninstall_requirements)
                except OSError:
                    pass
        else:
            to_install = [pkg for pkg in requirement_list if should_install_requirement(pkg)]
            logger.debug(f"Checking packages: {requirement_list}")
            logger.debug(f"Packages to install: {to_install}")

            if to_install:
                logger.info(f"Installing python packages {to_install}...")
                # Ensure target directory exists
                os.makedirs(target_destinations, exist_ok=True)
                for package in to_install:
                    run_cmd(
                        [sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', target_destinations, package])
            else:
                logger.info("Requirements already satisfied.")
    except Exception as e:
        logger.error(f"Error installing packages: {e}")
        if STRICT_MODE:
            raise


def uninstall_packages(requirement_list: Iterable[str]) -> None:
    """Uninstall Python packages."""
    to_remove = [requirement for requirement in requirement_list if should_uninstall_requirement(requirement)]
    if to_remove:
        for requirement in to_remove:
            logger.info(f"Uninstalling python package {requirement}...")
            try:
                run_cmd([sys.executable, '-m', 'pip', 'uninstall', '--yes', f'{requirement}'])
            except Exception as e:
                logger.error(f"Error uninstalling {requirement}: {e}")
                if STRICT_MODE:
                    raise
    else:
        logger.info("No packages to uninstall - requirements already satisfied.")


def debug_scan_directory(path: str) -> None:
    """Debug function to manually scan directory."""
    logger.info(f"=== MANUAL DIRECTORY SCAN: {path} ===")

    if not os.path.exists(path):
        logger.error(f"Directory does not exist: {path}")
        return

    entries = glob.glob(os.path.join(path, '*'))
    logger.info(f"Found {len(entries)} entries in {path}")

    for entry in entries[:10]:  # Show only first 10 to avoid spam
        name = os.path.basename(entry)
        manifest = os.path.join(entry, '__manifest__.py')
        requirements = os.path.join(entry, 'requirements.txt')

        logger.info(f"Entry: {name}")
        logger.info(f"  Path: {entry}")
        logger.info(f"  Is dir: {os.path.isdir(entry)}")
        logger.info(f"  Is symlink: {os.path.islink(entry)}")
        logger.info(f"  Has manifest: {os.path.exists(manifest)}")
        logger.info(f"  Has requirements: {os.path.exists(requirements)}")
        logger.info(f"  In IGNORE: {name in IGNORE}")
        logger.info("  ---")


def collect_links_and_deps(
        dir_addons: str,
        links_seek: Optional[List[Tuple[str, str]]] = None,
        depends: Optional[set] = None,
        main: Optional[List[str]] = None,
        install_requirements: Optional[bool] = None,
        priority: Optional[Sequence[str]] = None
) -> Tuple[List[Tuple[str, str]], set]:
    """Collect symlinks and dependencies from addon directories."""
    if not os.path.exists(dir_addons):
        logger.warning(f"Addon directory does not exist: {dir_addons}")
        return links_seek or [], depends or set()

    if depends is None:
        depends = set()
    if links_seek is None:
        links_seek = []
    if main is None:
        main = []
    priority_set = set(priority or ())

    logger.info(f"Scanning directory for addons: {dir_addons}")

    addon_count = 0
    found_addons = 0

    for entry in sorted(glob.glob(os.path.join(dir_addons, '*')),
                        key=lambda t: os.path.basename(t) in priority_set,
                        reverse=True):
        name = os.path.basename(entry)
        manifest_file = os.path.join(entry, '__manifest__.py')
        requirements_file = os.path.join(entry, "requirements.txt")

        addon_count += 1
        logger.debug(f"Checking entry: {name} -> {entry}")

        # Check for requirements file
        if os.path.exists(requirements_file) and install_requirements:
            logger.info(f"Found {requirements_file}, starting install")
            install_packages([], DEFAULT_PY_TARGET, requirements_file)

        # ОПРАВКА: Обработваме всички директории с manifest файл, не само symlinks
        if os.path.exists(manifest_file) and name not in IGNORE and os.path.isdir(entry):
            found_addons += 1
            links_seek.append((dir_addons, entry))
            logger.info(f"Found addon: {name} at {entry}")

            try:
                with open(manifest_file, 'r', encoding='utf-8') as manifest:
                    data = ast.literal_eval(manifest.read())

                if data.get('depends'):
                    for dep in data['depends']:
                        if dep not in main:
                            depends.add(dep)
                            logger.debug(f"Added dependency: {dep} from {name}")

                if data.get('external_dependencies') and data['external_dependencies'].get('python'):
                    logger.info(
                        f"Installing external dependencies for {name}: {data['external_dependencies']['python']}")
                    install_packages(data['external_dependencies']['python'], DEFAULT_PY_TARGET)
            except Exception as e:
                logger.error(f"Error processing manifest for {name}: {e}")

        elif os.path.isdir(entry) and name not in IGNORE:
            # Рекурсивно сканиране на поддиректории
            logger.debug(f"Recursively scanning subdirectory: {entry}")
            sub_links, sub_depends = collect_links_and_deps(
                entry, [], set(), main, install_requirements, priority=priority
            )
            links_seek.extend(sub_links)
            depends.update(sub_depends)

    logger.info(f"Scanned {addon_count} entries, found {found_addons} valid addons")
    logger.info(f"Total links to create: {len(links_seek)}")
    logger.info(f"Total dependencies: {len(depends)}")

    return links_seek, depends


def install_oca_addons(oca_folder: str) -> None:
    """Install OCA addons using oca-clone-everything."""
    logger.info(f"Installing OCA addons in {oca_folder}")
    os.makedirs(oca_folder, exist_ok=True)
    run_cmd(['oca-clone-everything', '--target-branch', f"{BRANCH}"], cwd=oca_folder)


def install_ee_addons(ee_folder: str, user: str, token: str) -> None:
    """Install Odoo Enterprise addons."""
    if not user or not token:
        logger.error("GitHub user and token are required for Enterprise installation")
        if STRICT_MODE:
            raise RuntimeError("GitHub credentials missing for Enterprise installation")
        return

    masked = f"{user}:***"
    logger.info(f"Installing Enterprise modules for {masked} in {ee_folder}")
    os.makedirs(ee_folder, exist_ok=True)
    run_cmd(['git', 'clone', '--branch', f"{BRANCH}", f'https://oauth2:{token}@github.com/odoo/enterprise.git'],
            cwd=ee_folder)


def github_credentials(user: Optional[str], token: Optional[str], email: Optional[str]) -> None:
    """Set up GitHub credentials."""
    if user and token and email and os.path.isfile(GITHUB_CRED_SCRIPT):
        logger.info(f"Setting up GitHub credentials for {user}")
        run_cmd([GITHUB_CRED_SCRIPT, '-u', user, '-t', token, '-e', email])
    else:
        logger.debug("Skipping GitHub credentials setup - missing parameters or script")


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
    """Set up OCA configuration."""
    config_oca = configparser.ConfigParser()
    cfg_path = os.path.join(oca_folder, 'oca.cfg')

    if os.path.exists(cfg_path):
        config_oca.read(cfg_path)

    update = update or not os.path.exists(cfg_path)
    if update:
        logger.info("Updating OCA configuration")

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

        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, 'w') as configfile:
            config_oca.write(configfile)


def get_config_print(config_file: configparser.ConfigParser) -> List[str]:
    """Get configuration as formatted strings for logging."""
    res: List[str] = []
    for section_line in config_file.sections():
        res.append(f"[{section_line}]")
        for items_key, items_val in config_file[section_line].items():
            # Mask passwords in logs
            if 'password' in items_key.lower() or 'token' in items_key.lower():
                items_val = '***' if items_val else ''
            res.append(f"{items_key} = {items_val}")
    return res


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Installing odoo modules.')
    parser.add_argument('conf', metavar='addons.conf', help='Configuration file')
    parser.add_argument('-a', '--odoo-addons-oca', dest='odoo_addons_oca', help='Odoo oca addons installation')
    parser.add_argument('-r', '--odoo-addons', dest='odoo_addons', help='Odoo addons installation')
    parser.add_argument('-s', '--source-dir', metavar='[full path]', dest='source_dir',
                        help='Source directory for addons. Example: /opt/odoo/odoo-18.0')
    parser.add_argument('-t', '--target-dir', metavar='[full path]', dest='target_dir',
                        help='Target directory for addons. Example: /var/lib/odoo/.local/share/Odoo/addons')
    parser.add_argument('--addons-oca', action='store_true', dest='use_oca', help='install all oca addons',
                        default=False)
    parser.add_argument('--force-update', action='store_true', dest='force_update',
                        help='Force update config files and permissions', default=False)
    parser.add_argument('--addons-ee', action='store_true', dest='use_ee', help='install all odoo enterprise addons',
                        default=False)
    parser.add_argument('--init-container', action='store_true', dest='init_container',
                        help='Enable strict init-container mode (fail fast, force requirements & update).',
                        default=False)
    parser.add_argument('-u', '--uid', dest='odoo_uid', help='Odoo owner UID')
    parser.add_argument('-g', '--gid', dest='odoo_gid', help='Odoo owner GID')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    return parser.parse_args()


def extract_settings_from_config(config: configparser.ConfigParser) -> Dict[str, object]:
    """Extract settings from configuration file."""
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
                    settings['priority_list'] += [v.strip() for v in value.split(',') if v.strip()]
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
    """Normalize comma-separated string to list."""
    if not value:
        return []
    return [v.strip() for v in value.split(',') if v.strip()]


def main() -> int:
    """Main function."""
    global STRICT_MODE

    args = parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate configuration file
    if not os.path.isfile(args.conf):
        logger.error(f"Configuration file not found: {args.conf}")
        return 1

    # Detect init mode via CLI or ENV
    env_init = os.getenv('ODOO_INIT_CONTAINER', '').strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    init_mode = bool(args.init_container or env_init)
    STRICT_MODE = init_mode

    logger.info(f"Starting supervisor with init_mode={init_mode}, strict_mode={STRICT_MODE}")

    # Set up directories
    opt_dir = DEFAULT_OPT_DIR
    source_dir = args.source_dir or f'{opt_dir}/odoo-{BRANCH}'
    odoo_dir = DEFAULT_ODOO_DIR
    target_dir = args.target_dir or f'{odoo_dir}/.local/share/Odoo/addons/{BRANCH}'
    oca_dir = f'{opt_dir}/oca'
    ee_dir = f'{opt_dir}/ee'
    folders = [target_dir, oca_dir, ee_dir]

    supervisor = f'{opt_dir}/supervisor.txt'
    init = not os.path.isfile(supervisor)

    # Set default UID/GID
    odoo_uid = int(args.odoo_uid) if args.odoo_uid is not None else 100
    odoo_gid = int(args.odoo_gid) if args.odoo_gid is not None else 100

    # Read configuration
    config = configparser.ConfigParser()
    config.read(args.conf, "utf-8")
    settings = extract_settings_from_config(config)

    # Apply configuration settings
    force_update = bool(settings['force_update']) or args.force_update
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

    use_oca = bool(settings['use_oca']) or args.use_oca
    use_ee = bool(settings['use_ee']) or args.use_ee
    odoo_addons_oca = settings['odoo_addons_oca']
    python_package = settings['python_package']

    # Init mode forces requirements and update to ensure full preparation
    if init_mode:
        use_requirements = True
        force_update = True

    logger.info(f"Configuration: source_dir={source_dir}, target_dir={target_dir}")
    logger.info(f"Settings: force_update={force_update}, use_requirements={use_requirements}")
    logger.info(f"Addons: use_oca={use_oca}, use_ee={use_ee}")

    # DEBUG: Show directory structure in verbose mode
    if args.verbose:
        debug_scan_directory(source_dir)

    # Create necessary folders
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        logger.debug(f"Created directory: {folder}")

    try:
        # Initialize or update configuration
        if not os.path.exists(supervisor) or force_update:
            logger.info("Initializing or updating supervisor configuration")

            try:
                run_cmd(['chown', '--recursive', f'{odoo_uid}:{odoo_gid}', odoo_dir])
            except Exception as e:
                logger.error(f"chown failed: {e}")
                if STRICT_MODE:
                    raise

            github_credentials(user_name, token, user_email)
            oca_credentials(user_name, token, odoo_user_name, odoo_user_password,
                            app_user_name, app_user_password, oca_dir, force_update)

            # Write supervisor log
            lines: List[str] = [
                f"Force update: {force_update}\n",
                f"chown {odoo_uid}:{odoo_gid} {odoo_dir}\n",
                f"Write github credentials: {user_name}:{'***' if token else token}:{user_email}\n",
                f"Write oca credentials: {user_name}, {'***' if token else token}, {odoo_user_name}, ***\n",
                f"Configurations: {args.conf}\n",
            ]
            lines.extend(get_config_print(config))
            lines.append("\n")

            os.makedirs(os.path.dirname(supervisor), exist_ok=True)
            with open(supervisor, "w") as file:
                file.writelines(lines)
            logger.info(f"Supervisor configuration written to {supervisor}")

        # Handle package uninstalls
        if python_package:
            UNINSTALL[:] = normalize_list(python_package)
            if UNINSTALL:
                logger.info(f"Uninstalling packages: {UNINSTALL}")
                uninstall_packages(UNINSTALL)

        # Prepare OCA/EE trees
        if init and use_oca:
            install_oca_addons(oca_dir)
        elif force_update and not init and use_oca:
            recursive_git_pull(oca_dir)

        if init and use_ee:
            if not token and STRICT_MODE:
                raise RuntimeError("Enterprise installation requested but GitHub token is missing.")
            install_ee_addons(ee_dir, user_name or '', token or '')
        elif force_update and not init and use_ee:
            recursive_git_pull(ee_dir)

        # Install explicit addons lists
        if args.odoo_addons_oca or odoo_addons_oca:
            packages = normalize_list(args.odoo_addons_oca or odoo_addons_oca)
            logger.info(f"Installing OCA addons: {packages}")
            install_packages(packages, DEFAULT_EXTRA_ADDONS)

        if getattr(args, 'odoo_addons', None):
            packages = normalize_list(args.odoo_addons)
            logger.info(f"Installing Odoo addons: {packages}")
            install_packages(packages, DEFAULT_EXTRA_ADDONS)

        # Install global requirements
        etc_requirements = os.path.join('/etc', 'odoo', "requirements.txt")
        if os.path.isfile(etc_requirements):
            logger.info("Installing global requirements")
            install_packages([], DEFAULT_PY_TARGET, etc_requirements)

        # Scan source directory and collect links/dependencies
        logger.info(f"Scanning source directory: {source_dir}")
        links, dependencies = collect_links_and_deps(
            source_dir, install_requirements=use_requirements, priority=priority_list
        )
        addons: List[str] = list(dependencies)

        logger.info(f"Found {len(links)} addon links and {len(addons)} dependencies")

        if not links:
            logger.warning("No addons found! Please check your source directory and manifest files.")
            logger.info(f"Searched in: {source_dir}")
            logger.info("Make sure directories contain __manifest__.py files")

        # Create symlinks for collected addons
        symlinks_created = 0
        symlinks_skipped = 0

        for dir_addons, entry in links:
            source_path = entry
            addon_name = os.path.basename(entry)
            target_path = os.path.join(target_dir, addon_name)

            logger.debug(f"Processing addon: {addon_name}")
            logger.debug(f"  Source: {source_path}")
            logger.debug(f"  Target: {target_path}")

            # ОПРАВКА: Създаваме симлинк за всички намерени модули
            try:
                if os.path.islink(target_path):
                    # Проверяваме дали симлинкът сочи към правилното място
                    current_target = os.readlink(target_path)
                    if current_target == source_path:
                        logger.debug(f'Symlink already correct: {source_path} -> {target_path}')
                        symlinks_skipped += 1
                        continue
                    else:
                        logger.info(f'Updating symlink: {target_path} from {current_target} to {source_path}')
                        os.unlink(target_path)

                elif os.path.exists(target_path):
                    logger.warning(f'Target exists (not symlink): {target_path}')
                    symlinks_skipped += 1
                    continue

                # Създаваме симлинка
                os.symlink(source_path, target_path)
                logger.info(f'✓ Symbolic link created: {source_path} -> {target_path}')
                symlinks_created += 1

            except FileExistsError:
                logger.debug(f'Target already exists: {target_path}')
                symlinks_skipped += 1
            except Exception as e:
                logger.error(f'Error creating symlink {source_path} -> {target_path}: {e}')

        logger.info(f"Symlink summary: {symlinks_created} created, {symlinks_skipped} skipped")

        # Final permissions update
        if force_update or init:
            logger.info("Updating file permissions...")
            recursive_file_permissions(odoo_dir, odoo_uid, odoo_gid)

        # Success summary
        logger.info("Supervisor completed successfully!")
        print(f"""
═══════════════════════════════════════════════════════════════
🎉 SUPERVISOR ЗАВЪРШЕН УСПЕШНО! 🎉
═══════════════════════════════════════════════════════════════

📊 Резултати:
   • Odoo директория: {odoo_dir}
   • Принудително обновяване: {force_update}
   • Използване на requirements: {use_requirements}
   • Източник: {source_dir}
   • Цел: {target_dir}
   • Собственик: {odoo_uid}:{odoo_gid}
   • Създадени symlinks: {symlinks_created}
   • Намерени зависимости: {len(addons)}

═══════════════════════════════════════════════════════════════
        """)
        return 0

    except Exception as e:
        logger.error(f"Supervisor failed with error: {e}")
        if STRICT_MODE:
            logger.error("Running in strict mode - exiting with error code")
        return 1


if __name__ == '__main__':
    sys.exit(main())
