import logging
from typing import Any
from typing import Tuple

from docker import DockerClient
from docker.errors import APIError
from docker.errors import ContainerError
from docker.errors import DockerException
from docker.errors import ImageNotFound

from skilletlib.exceptions import *
from .base import Snippet
import time

logger = logging.getLogger(__name__)


class DockerSnippet(Snippet):
    """
    Docker Snippet - Represents a command to run inside a docker container
    """
    required_metadata = {'name', 'image', 'cmd'}

    # optional parameters that may be set in the snippet metadata
    optional_metadata = {
        'volumes': dict(),
        'async': True
    }

    output_type = 'text'

    # keep track of the last time we queried the logs
    last_logs_time = None

    def __init__(self, metadata):
        super().__init__(metadata)
        self.client = DockerClient()

        # configure from metadata
        image = self.metadata.get('image', 'python')
        if ':' in image:
            self.image, self.tag = image.split(':')

        else:
            self.image = image
            self.tag = 'latest'

        self.working_dir = self.metadata.get('working_dir', '/app')

        # this is set in the get_snippets method of the Docker Skillet class
        # and is used if no volume mounts have been specified
        self.path = self.metadata.get('skillet_path', None)

        self.detach = self.metadata.get('async', False)

        if self.detach:
            self.auto_remove = False
        else:
            self.auto_remove = True

        # set up volumes
        # A dictionary to configure volumes mounted inside the container.
        # The key is either the host path or a volume name, and the value is a dictionary with the keys:
        #     bind The path to mount the volume inside the container
        #     mode Either rw to mount the volume read/write, or ro to mount it

        volumes = self.metadata.get('volumes', dict())

        if not volumes:
            self.volumes = {self.path: {'bind': self.working_dir, 'mode': 'rw'}}

        else:
            self.volumes = volumes
            # if we have a volume passed in, ensure the working dir is set to the path of this skillet so
            # relative commands will work as intended
            self.working_dir = self.path

        # track our container
        self.container_id = ''

    def render_metadata(self, context: dict) -> dict:
        """
        Renders each item in the metadata using the provided context.
        Currently renders the cmd attribute only
        :param context: dict containing key value pairs to
        :return: dict containing the snippet definition metadata with the attribute values rendered accordingly
        """

        # execute super render_metadata
        # this will set the passed context onto self.context
        meta = super().render_metadata(context)

        try:
            if 'cmd' in self.metadata:
                meta['cmd'] = self.render(self.metadata['cmd'], context)

        except TypeError as te:
            logger.info(f'Could not render metadata for snippet: {self.name}: {te}')

        return meta

    def execute(self, context) -> Tuple[str, str]:
        """
        Execute this cmd in the specified docker container
        :param context: context containing all the user-supplied input variables. Also contains output from previous
        steps. Raises SkilletLoaderException on error
        :return:  Tuple(dict, str) output and string representing 'success' or 'failure'
        """
        try:

            output = ''
            logger.info(f'Pulling image: {self.image} with tag: {self.tag}')
            # self.client.images.pull(self.image, self.tag)

            vols = self.volumes

            image = self.image + ":" + self.tag
            logger.info(f'Creating container...')
            return_data = self.client.containers.run(image, self.metadata['cmd'], volumes=vols, stderr=True,
                                                     detach=self.detach, working_dir=self.working_dir,
                                                     auto_remove=self.auto_remove, environment=context)

            if self.detach:
                # return_data will be a Container object if self.detach is True
                self.container_id = return_data.id
                output = self.container_id
                print('container id is ' + self.container_id)
                return output, 'running'

            else:
                # return_data will be the bytes returned from the command
                if type(return_data) is bytes:
                    return_str = return_data.decode('UTF-8')
                    return return_str, 'success'
                else:
                    return return_data, 'success'

        except ImageNotFound:
            raise SkilletLoaderException(f'Could not locate image {self.image} in {self.name}')
        except APIError as ae:
            raise SkilletLoaderException(f'Error communicating with Docker API: {ae}')
        except ContainerError as ce:
            raise SkilletLoaderException(f'Container command failed: {ce}')
        except DockerException as de:
            raise SkilletLoaderException(f'Could not execute docker container {self.name}: {de}')

    def get_container(self):
        try:
            return self.client.containers.get(self.container_id)
        except DockerException as de:
            logger.error(de)
            logger.error('Could not get container!')
            return None

    def get_output(self) -> Tuple[str, str]:
        if not self.detach:
            return '', 'success'

        try:
            container = self.get_container()

            if self.last_logs_time is None:
                return_data = container.logs()
            else:
                return_data = container.logs(since=self.last_logs_time)

            self.last_logs_time = int(time.time())

            return_str = self.__clean_output(return_data)

            if container.status == 'running':
                return return_str, 'running'

            else:
                logger.info(container.status)
                return return_str, 'success'

        except APIError as ae:
            raise SkilletLoaderException(f'Could not get logs for {self.name}: {ae}')

    def cleanup(self) -> None:
        """
        Clean up action is the docker container was started with 'async', no-op is async is False
        :return: None
        """
        if not self.detach:
            return

        try:
            container = self.get_container()

            if container:
                if container.status != 'running':
                    container.remove()
                else:
                    logger.warning(f'Docker container {self.container_id} may need to be manually removed!')

        except APIError as ae:
            raise SkilletLoaderException(f'Could not clean up {self.name}: {ae}')

    @staticmethod
    def __clean_output(return_data: Any) -> str:
        if type(return_data) is bytes:
            return_str = return_data.decode('UTF-8')
            return return_str
        else:
            return str(return_data)
