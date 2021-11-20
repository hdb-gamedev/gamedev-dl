from zipfile import ZipFile
from pathlib import Path
import subprocess
import re
from bs4 import BeautifulSoup
import win32com.client
import sys
from gooey import Gooey, GooeyParser
import asyncio
import aiofiles
import aiohttp

if getattr(sys, 'frozen', False):
    datapath = Path(sys._MEIPASS)
    delete_path = selfpath = Path(sys.executable)
else:
    selfpath = Path(__file__)
    datapath = selfpath.parent
    delete_path = None
log = print


async def get_release_url(session, repo, suffix):
    url = f'https://api.github.com/repos/{repo}/releases/latest'
    log(f'Looking at {url}...')
    r = await session.get(url, headers={'Accept': 'application/vnd.github.v3+json'})
    for asset in (await r.json())['assets']:
        if asset['name'].endswith(suffix):
            log(f'Found asset {asset["name"]}, ending with {suffix}')
            return asset['url']


def makeshortcut(shortcut_path, target):
    log(f'Creating shortcut to {target} at {shortcut_path}')
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path.resolve()))
    shortcut.Targetpath = str(target.resolve())
    shortcut.save()


async def download(session, url, path, headers={}):
    log(f'Downloading {url} to {path}')
    async with session.get(url, headers=headers) as response:
        async with aiofiles.open(path, 'wb') as f:
            await f.write(await response.read())
            # async for chunk in response.content.iter_chunked(1024*1024):
            #     await f.write(chunk)


async def gettext(session, url, headers={}):
    log(f'Reading {url}')
    async with session.get(url, headers=headers) as response:
        return await response.text()


async def extract_zip(zippath, folder_path):
    log(f'Extracting {zippath} to {folder_path}...')
    with ZipFile(zippath) as z:
        infolist = z.infolist()
        for member in infolist:
            z.extract(member, folder_path)
            await asyncio.sleep(0)


def heading(name, url):
    log(f'Starting {name}')


def finished(name):
    log(f'Finished {name}')


async def download_godot(session, dlpath, shortcut_folder):
    heading('Godot', 'https://godotengine.org/download/windows')
    shortcut_path = Path(shortcut_folder, 'Godot.lnk')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    log("Finding latest Godot version...")
    url = await get_release_url(session, 'godotengine/godot', 'stable_win64.exe.zip')
    zippath = Path(dlpath, "godot.exe.zip")

    await download(session, url, zippath, headers={'Accept': 'application/octet-stream'})

    log(f'Extracting {zippath}')
    godot_exe = None
    await extract_zip(zippath, dlpath)
    log(f'Deleting {zippath}')
    zippath.unlink()

    godot_exe = next(dlpath.glob("Godot*.exe"))

    makeshortcut(shortcut_path, Path(dlpath, godot_exe))
    finished('Godot')


async def extract_7z(sevenzip_location, archive, outpath):
    log(f'Using 7zip at {sevenzip_location}')
    log(f'Extracting {archive} with 7zip...')
    proc = await asyncio.create_subprocess_exec(str(sevenzip_location), 'x', '-y', '-aos',
                                                f'{archive}', f'-o{outpath}', stdout=asyncio.subprocess.
                                                PIPE)

    await proc.wait()
    if proc.returncode != 0:
        raise ValueError(f'7zip failed extracting {sevenzip_location}')


async def download_github_desktop(session, dlpath, shortcut_folder, clone_repo):
    heading('Github Desktop', 'https://desktop.github.com/')
    sevenzip_location = Path(datapath, '7z/7z.exe')
    shortcut_path = Path(shortcut_folder, 'GithubDesktop.lnk')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    setup_exe_path = Path(dlpath, 'GithubDestkopSetup-x64.exe')
    setup_exe_contents_path = Path(dlpath, 'GithubDestkop')
    url = 'https://central.github.com/deployments/desktop/desktop/latest/win32'

    await download(session, url, setup_exe_path)

    await extract_7z(sevenzip_location, setup_exe_path, setup_exe_contents_path)

    log(f'Deleting {setup_exe_path}')
    setup_exe_path.unlink()

    nupkg_path = next(setup_exe_contents_path.glob("*.nupkg"))

    await extract_7z(sevenzip_location, nupkg_path, setup_exe_contents_path)

    github_desktop_exe_path = Path(
        setup_exe_contents_path, 'lib', 'net45', 'GithubDesktop.exe')
    log(f'Github Desktop at {github_desktop_exe_path}')
    makeshortcut(shortcut_path, github_desktop_exe_path)

    finished('Github Desktop')

    if clone_repo:
        await clone_samples(clone_repo, dlpath=shortcut_folder, gitdlpath=dlpath)


async def download_blender(session, dlpath, shortcut_folder):
    heading('Blender', 'https://www.blender.org/download/')
    shortcut_path = Path(shortcut_folder, 'Blender.lnk')
    folder_path = Path(dlpath, 'blender')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    releases_url = "https://mirror.clarkson.edu/blender/release/"
    log(f'Finding latest Blender version at {releases_url}')
    releases_soup = BeautifulSoup(await gettext(session, releases_url), features='lxml')
    folder_link = releases_soup.find_all(
        'a', href=re.compile(r'Blender\d+\.\d+/'))[-1]
    release_folder_url = releases_url+folder_link['href']

    log(f"Finding Blender download at {release_folder_url}")
    release_folder_soup = BeautifulSoup(await gettext(session, release_folder_url), features='lxml')
    download_link = release_folder_soup.find_all(
        'a', href=re.compile(r'.*windows.*64.*\.zip'))[-1]
    download_path = release_folder_url+download_link['href']

    zippath = Path(dlpath, 'blender.zip')
    await download(session, download_path, zippath)

    await extract_zip(zippath, folder_path)
    with ZipFile(zippath) as z:
        z.extractall(folder_path)
    log(f'Deleting {zippath}')
    zippath.unlink()

    blender_exe = next(folder_path.glob("*/blender.exe"))
    makeshortcut(shortcut_path, blender_exe)
    finished('Blender')


async def download_krita(session, dlpath, shortcut_folder):
    heading('Krita', 'https://krita.org/en/download/krita-desktop/')
    folder_path = Path(dlpath, 'krita')
    shortcut_path = Path(shortcut_folder, 'Krita.lnk')
    if shortcut_path.exists():
        log(f'Already have {shortcut_path}')
        return
    releases_url = "https://download.kde.org/stable/krita/"
    log(f'Finding latest Krita version at {releases_url}')
    releases_soup = BeautifulSoup(await gettext(session, releases_url), features='lxml')
    folder_link = releases_soup.find_all(
        'a', href=re.compile(r'\d+\.\d+\.\d+/'))[-1]
    release_folder_url = releases_url+folder_link['href']

    log(f"Finding Krita download at {release_folder_url}")
    release_folder_soup = BeautifulSoup(await gettext(session, release_folder_url), features='lxml')
    download_link = release_folder_soup.find_all(
        'a', href=re.compile(r'krita-x64-.*\.zip'))[-1]
    download_path = release_folder_url+download_link['href']

    zippath = Path(dlpath, 'krita.zip')
    await download(session, download_path, zippath)

    log(f'Extracting {zippath} to {folder_path}...')
    await extract_zip(zippath, folder_path)
    log(f'Deleting {zippath}')
    zippath.unlink()

    krita_exe = next(folder_path.glob("*/bin/krita.exe"))
    makeshortcut(shortcut_path, krita_exe)
    finished('Krita')


async def clone_samples(repo, dlpath, gitdlpath):
    heading('Samples', 'https://github.com/hdb-gamedev/godot-samples')
    gitpath = Path(
        gitdlpath, 'GithubDestkop/lib/net45/resources/app/git/cmd/git.exe')
    log(f'using {gitpath} to clone {repo}')
    await asyncio.create_subprocess_exec(str(gitpath.resolve()), 'clone', repo,
                                         cwd=dlpath, stdout=asyncio.subprocess.PIPE)
    finished('Samples')


# @Gooey(program_name='Gamedev Club Installer')
def main():
    default_download_message = ''
    default_download_folder = selfpath.resolve().parent
    if all(x == selfpath for x in default_download_folder.iterdir()):
        default_download_message = f'Defaulting download folder to {default_download_folder}, since it is empty besides this exe'
    else:
        default_download_folder = Path(default_download_folder, 'gamedev')
        default_download_message = f'Defaulting download folder to {default_download_folder}, since this directory has other things in it'
    log(default_download_message)
    # default_shortcut_folder = Path(Path.home(), 'Desktop')
    default_shortcut_folder = default_download_folder
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

    async def run_all():
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                download_godot(session, arguments.download_folder,
                               arguments.shortcut_folder),
                # download_github_desktop(session, arguments.download_folder,
                #                         arguments.shortcut_folder, clone_repo=arguments.clone_repo),
                # download_blender(
                #     session, arguments.download_folder, arguments.shortcut_folder),
                # download_krita(session, arguments.download_folder,
                #                arguments.shortcut_folder)
            )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_all())

    # if delete_path is not None:
    #     log(f"This is when I would schedule {delete_path} for deletion")


if __name__ == '__main__':
    main()
