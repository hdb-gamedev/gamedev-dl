import requests
from zipfile import ZipFile
from pathlib import Path
import subprocess
import re
from bs4 import BeautifulSoup
import win32com.client
import sys
from gooey import Gooey, GooeyParser

if getattr(sys, 'frozen', False):
    datapath = Path(sys._MEIPASS)
    delete_path = selfpath = Path(sys.executable)
else:
    selfpath = Path(__file__)
    datapath = selfpath.parent
    delete_path = None

log = print


def get_release_url(repo, suffix):
    url = f'https://api.github.com/repos/{repo}/releases/latest'
    log(f'Looking at {url}...')
    r = requests.get(url, headers={'Accept': 'application/vnd.github.v3+json'})
    for asset in r.json()['assets']:
        if asset['name'].endswith(suffix):
            log(f'Found asset {asset["name"]}, ending with {suffix}')
            return asset['url']


def makeshortcut(shortcut_path, target):
    log(f'Creating shortcut to {target} at {shortcut_path}')
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path.resolve()))
    shortcut.Targetpath = str(target.resolve())
    shortcut.save()


def log_progress(progress):
    log(f'Progress: {int(progress*100)}%')


def download(url, path, headers={}):
    if path.exists():
        log(f'Already have {path}')
        return
    response = requests.get(url, stream=True, headers=headers)
    size = int(response.headers.get('content-length', 0))
    block_size = 1024
    log(f'Downloading {url} to {path}')
    progress = 0
    numblocks = 0
    log_progress(0)
    with open(path, 'wb') as f:
        for data in response.iter_content(block_size):
            f.write(data)
            numblocks += 1
            if numblocks % 5000 == 0:
                log_progress(numblocks*block_size / size)
    log_progress(1)


def extract_zip(zippath, folder_path):
    log(f'Extracting {zippath} to {folder_path}...')
    with ZipFile(zippath) as z:
        infolist = z.infolist()
        progress = 0
        log_progress(0)
        for i, member in enumerate(infolist):
            z.extract(member, folder_path)
            if i % 100 == 0:
                log_progress(i / len(infolist))
        log_progress(1)


heading_printed = False


def heading(name, url):
    global heading_printed
    if heading_printed:
        log()
    heading_printed = True
    log(name)
    log(url)


def download_godot(dlpath, shortcut_folder):
    heading('Godot', 'https://godotengine.org/download/windows')
    shortcut_path = Path(shortcut_folder, 'Godot.lnk')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    log("Finding latest Godot version...")
    url = get_release_url('godotengine/godot', 'stable_win64.exe.zip')
    zippath = Path(dlpath, "godot.exe.zip")

    download(url, zippath, headers={'Accept': 'application/octet-stream'})

    log(f'Extracting {zippath}')
    godot_exe = None
    with ZipFile(zippath) as z:
        for member in z.infolist():
            godot_exe = member.filename
            z.extract(member, dlpath)
    log(f'Deleting {zippath}')
    zippath.unlink()

    makeshortcut(shortcut_path, Path(dlpath, godot_exe))


def download_github_desktop(dlpath, shortcut_folder):
    heading('Github Desktop', 'https://desktop.github.com/')
    sevenzip_location = Path(datapath, '7z/7z.exe')
    shortcut_path = Path(shortcut_folder, 'GithubDesktop.lnk')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    setup_exe_path = Path(dlpath, 'GithubDestkopSetup-x64.exe')
    setup_exe_contents_path = Path(dlpath, 'GithubDestkop')
    url = 'https://central.github.com/deployments/desktop/desktop/latest/win32'

    download(url, setup_exe_path)

    log(f'Using 7zip at {sevenzip_location}')
    log(f'Extracting {setup_exe_path} with 7zip...')
    x = subprocess.run([str(sevenzip_location), 'x', '-y', '-aos',
                        f'{setup_exe_path}', f'-o{setup_exe_contents_path}'], stdout=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    if x.returncode != 0:
        raise ValueError('7zip failed')

    log(f'Deleting {setup_exe_path}')
    setup_exe_path.unlink()

    nupkg_path = next(setup_exe_contents_path.glob("*.nupkg"))

    log(f'Extracting {nupkg_path} with 7zip...')
    x = subprocess.run([str(sevenzip_location), 'x', '-y', '-aos',
                        f'{nupkg_path}', f'-o{setup_exe_contents_path}'], stdout=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    if x.returncode != 0:
        raise ValueError('7zip failed')

    github_desktop_exe_path = Path(
        setup_exe_contents_path, 'lib', 'net45', 'GithubDesktop.exe')
    log(f'Github Desktop at {github_desktop_exe_path}')
    makeshortcut(shortcut_path, github_desktop_exe_path)


def download_blender(dlpath, shortcut_folder):
    heading('Blender', 'https://www.blender.org/download/')
    shortcut_path = Path(shortcut_folder, 'Blender.lnk')
    folder_path = Path(dlpath, 'blender')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    releases_url = "https://mirror.clarkson.edu/blender/release/"
    log(f'Finding latest Blender version at {releases_url}')
    releases_soup = BeautifulSoup(requests.get(
        releases_url).content, features='lxml')
    folder_link = releases_soup.find_all(
        'a', href=re.compile(r'Blender\d+\.\d+/'))[-1]
    release_folder_url = releases_url+folder_link['href']

    log(f"Finding Blender download at {release_folder_url}")
    release_folder_soup = BeautifulSoup(requests.get(
        release_folder_url).content, features='lxml')
    download_link = release_folder_soup.find_all(
        'a', href=re.compile(r'.*windows.*64.*\.zip'))[-1]
    download_path = release_folder_url+download_link['href']

    zippath = Path(dlpath, 'blender.zip')
    download(download_path, zippath)

    extract_zip(zippath, folder_path)
    with ZipFile(zippath) as z:
        z.extractall(folder_path)
    log(f'Deleting {zippath}')
    zippath.unlink()

    blender_exe = next(folder_path.glob("*/blender.exe"))
    makeshortcut(shortcut_path, blender_exe)


def download_krita(dlpath, shortcut_folder):
    heading('Krita', 'https://krita.org/en/download/krita-desktop/')
    folder_path = Path(dlpath, 'krita')
    shortcut_path = Path(shortcut_folder, 'Krita.lnk')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    releases_url = "https://download.kde.org/stable/krita/"
    log(f'Finding latest Krita version at {releases_url}')
    releases_soup = BeautifulSoup(requests.get(
        releases_url).content, features='lxml')
    folder_link = releases_soup.find_all(
        'a', href=re.compile(r'\d+\.\d+\.\d+/'))[-1]
    release_folder_url = releases_url+folder_link['href']

    log(f"Finding Krita download at {release_folder_url}")
    release_folder_soup = BeautifulSoup(requests.get(
        release_folder_url).content, features='lxml')
    download_link = release_folder_soup.find_all(
        'a', href=re.compile(r'krita-x64-.*\.zip'))[-1]
    download_path = release_folder_url+download_link['href']

    zippath = Path(dlpath, 'krita.zip')
    download(download_path, zippath)

    log(f'Extracting {zippath} to {folder_path}...')
    extract_zip(zippath, folder_path)
    log(f'Deleting {zippath}')
    zippath.unlink()

    krita_exe = next(folder_path.glob("*/bin/krita.exe"))
    makeshortcut(shortcut_path, krita_exe)


def clone_samples(repo, dlpath, gitdlpath):
    gitpath = Path(
        gitdlpath, 'GithubDestkop/lib/net45/resources/app/git/cmd/git.exe')
    log(f'using {gitpath} to clone {repo}')
    subprocess.run([str(gitpath.resolve()), 'clone', repo],
                   cwd=dlpath, stdout=subprocess.PIPE)


@Gooey(progress_regex=r'^Progress: (\d+)%$', program_name='Gamedev Club Installer')
def main():
    default_download_message = ''
    default_download_folder = selfpath.resolve().parent
    if all(x == selfpath for x in default_download_folder.iterdir()):
        default_download_message = f'Defaulting download folder to {default_download_folder}, since it is empty besides this exe'
    else:
        default_download_folder = Path(default_download_folder, 'gamedev')
        default_download_message = f'Defaulting download folder to {default_download_folder}, since this directory has other things in it'
    log(default_download_message)
    default_shortcut_folder = Path(Path.home(), 'Desktop')
    #default_shortcut_folder = default_download_folder
    log(f'Shortcuts folder defaulting to {default_shortcut_folder}')

    parser = GooeyParser(
        description="Downloads Godot, Github Desktop, Blender, and Krita")
    group = parser.add_argument_group("Options", gooey_options={
        'columns': 1
    })
    group.add_argument('--download-folder', metavar='Download Folder', type=Path,
                       widget='DirChooser', default=str(default_download_folder),
                       help=f"Where to download all the files (they can't be moved later or the shortcuts will be wrong)")
    group.add_argument('--shortcut-folder', metavar='Shortcut Folder', type=Path,
                       widget='DirChooser', default=str(default_shortcut_folder),
                       help="Where to put shortcuts that you use to launch the programs",
                       gooey_options={
                           'default_path': str(default_shortcut_folder)
                       })
    group.add_argument('--clone-repo', metavar='Download Godot Samples', help='Clone this repository (to the same folder as the shortcuts)',
                       default='https://github.com/hdb-gamedev/godot-samples.git')

    arguments = parser.parse_args()

    arguments.download_folder.mkdir(parents=True, exist_ok=True)
    arguments.shortcut_folder.mkdir(parents=True, exist_ok=True)

    download_godot(arguments.download_folder, arguments.shortcut_folder)
    download_github_desktop(arguments.download_folder,
                            arguments.shortcut_folder)
    download_blender(arguments.download_folder, arguments.shortcut_folder)
    download_krita(arguments.download_folder, arguments.shortcut_folder)

    if arguments.clone_repo:
        clone_samples(arguments.clone_repo,
                      arguments.shortcut_folder, arguments.download_folder)

    # if delete_path is not None:
    #     log(f"This is when I would schedule {delete_path} for deletion")


if __name__ == '__main__':
    main()
