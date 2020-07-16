import os
import pathlib


def setup_dir():
    current_path = pathlib.Path('.').resolve().name
    if current_path == 'skilletlib':
        os.chdir('./tests')
