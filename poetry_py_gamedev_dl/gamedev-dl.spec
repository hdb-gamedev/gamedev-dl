# -*- mode: python ; coding: utf-8 -*-
import gooey

gooey_root = os.path.dirname(gooey.__file__)
gooey_languages = Tree(os.path.join(
    gooey_root, 'languages'), prefix='gooey/languages')
gooey_images = Tree(os.path.join(gooey_root, 'images'), prefix='gooey/images')

block_cipher = None


a = Analysis(['__main__.py'],
             pathex=[r'C:\Users\josh\Desktop\py-gamdev-dl\poetry-py-gamedev-dl\poetry_py_gamedev_dl\__main__.py'],
             binaries=[],
             datas=[('7z', '7z')],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

options = [('u', None, 'OPTION')]

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          options,
          gooey_languages,
          gooey_images,
          name='gamedev-dl',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon="NONE")
