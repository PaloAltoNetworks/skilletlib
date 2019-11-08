import logging
import os
import shutil

from git import Repo

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
            logger.debug("Updating repository...")
            self.Repo.remotes.origin.pull()
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
