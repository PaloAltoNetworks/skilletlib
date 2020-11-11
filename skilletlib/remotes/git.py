# Copyright (c) 2020, Palo Alto Networks
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Authors: Adam Baumeister, Nathan Embery

import logging
import os
import shutil

from git import Repo
from git.exc import GitCommandError

from skilletlib.exceptions import SkilletLoaderException

logger = logging.getLogger(__name__)


class Git:
    """
    Git remote
    This class provides an interface to Github repositories containing Skillets or XML snippets.
    """

    def __init__(self, repo_url, store=os.getcwd()):
        """
        Initialize a new Git repo object

        :param repo_url: URL path to repository.
        :param store: Directory to store repository in. Defaults to the current directory.
        """

        if not self.check_git_exists():
            raise SkilletLoaderException('A git client must be installed to use this remote!')

        self.repo_url = repo_url
        self.store = store
        self.Repo = None
        self.name = ''
        self.path = ''
        self.update = ''

    def clone(self, name: str) -> str:
        """
        Clone a remote directory into the store.

        :param name: Name of repository
        :return: (string): Path to cloned repository
        """
        if not name:
            raise ValueError("Missing or bad name passed to Clone command.")

        self.name = name
        path = self.store + os.sep + name
        self.path = path

        if os.path.exists(path):
            self.Repo = Repo(path)

            # FIX for #56
            if self.repo_url not in self.Repo.remotes.origin.urls:
                logger.info('Found new remote URL for this named repo')

                try:
                    # only recourse is to remove the .git directory
                    if os.path.exists(os.path.join(path, '.git')):
                        shutil.rmtree(path)

                    else:
                        raise SkilletLoaderException('Refusing to remove non-git directory')

                except OSError:
                    raise SkilletLoaderException('Repo directory exists!')

                logger.debug("Cloning into {}".format(path))

                try:
                    self.Repo = Repo.clone_from(self.repo_url, path)

                    # ensure all submodules are also updated and available
                    self.Repo.submodule_update(recursive=False)

                except GitCommandError as gce:
                    raise SkilletLoaderException(f'Could not clone repository {gce}')

            else:
                logger.debug("Updating repository...")

                try:
                    self.Repo.remotes.origin.pull()

                except GitCommandError as gce:
                    logger.error('Could not clone repository!')
                    raise SkilletLoaderException(f'Error Cloning repository {gce}')

            return path

        else:
            logger.debug("Cloning into {}".format(path))
            self.Repo = Repo.clone_from(self.repo_url, path)

        self.path = path
        return path

    def branch(self, branch_name: str) -> None:
        """
        Checkout the specified branch.

        :param branch_name: Branch to checkout.
        :return: None
        """
        logger.debug("Checking out: " + branch_name)

        if self.update:
            logger.debug("Updating branch.")
            self.Repo.remotes.origin.pull()

        self.Repo.git.checkout(branch_name)

    @staticmethod
    def check_git_exists():
        return shutil.which("git")

    def get_submodule_dirs(self, path=None) -> list:
        """
        Return a list of submodule directories if any. This is used to load and resolve skillets into the
        resolved_skillets list. This allows multiple projects to use the same base skillets without
        conflicts at the application layer.

        :param path: path to
        :return:
        """

        submodule_list = list()

        if path is not None:
            self.path = path

        try:

            if self.Repo is None:
                self.Repo = Repo(self.path)

            submodules = self.Repo.submodules
            for sm in submodules:
                submodule_list.append(sm.path)

            return submodule_list

        except GitCommandError as gce:
            logger.info('This repository is not a git repository')
            logger.info(f'Error was {gce}')
            return []
