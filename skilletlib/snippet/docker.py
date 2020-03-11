import logging
from typing import Tuple

from docker import DockerClient
from docker.errors import APIError
from docker.errors import ContainerError
from docker.errors import DockerException
from docker.errors import ImageNotFound

from skilletlib.exceptions import *
from .base import Snippet

logger = logging.getLogger(__name__)


class DockerSnippet(Snippet):
    """
    Docker Snippet - Represents a command to run inside a docker container
    """
    required_metadata = {'name', 'image', 'cmd'}

    # optional parameters that may be set in the snippet metadata
    optional_metadata = {
        'volumes': dict(),
        'async': False
    }

    output_type = 'text'

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

        self.cmd = self.metadata.get('cmd', 'echo "you forgot a cmd silly"')
        self.working_dir = self.metadata.get('working_dir', '/app')

        # this is set in the get_snippets method of the Docker Skillet class
        # and is used if no volume mounts have been specified
        self.path = self.metadata.get('skillet_path', None)

        self.detach = self.metadata.get('async', False)

        # set up volumes
        # A dictionary to configure volumes mounted inside the container.
        # The key is either the host path or a volume name, and the value is a dictionary with the keys:
        #     bind The path to mount the volume inside the container
        #     mode Either rw to mount the volume read/write, or ro to mount it

        # FIXME - this should be a fallback only -
        #  if skilletlib is running in a container itself,
        #  the self.path mount will be incorrect from the host perspective, we need to mount 'volumes-from'
        #  the skilletlib host container. The hosting application should handle this, but we need
        #  to add the hooks here to allows a 'volumes-from' or a way to set the volumes dynamically

        volumes = self.metadata.get('volumes', dict())

        if not volumes:
            self.volumes = {self.path: {'bind': self.working_dir, 'mode': 'rw'}}

        else:
            # FIXME - need to validate nothing too bad can happen here :-/
            self.volumes = volumes

        # track our container
        self.container_id = ''

    def execute(self, context) -> Tuple[dict, str]:
        try:

            output = dict()
            logger.info(f'Pulling image: {self.image} with tag: {self.tag}')
            # self.client.images.pull(self.image, self.tag)

            vols = self.volumes

            image = self.image + ":" + self.tag
            logger.info(f'Creating container...')
            return_data = self.client.containers.run(image, self.cmd, volumes=vols,
                                                     detach=self.detach, working_dir=self.working_dir,
                                                     auto_remove=False, environment=context)

            if self.detach:
                # return_data will be a Container object if self.detach is True
                self.container_id = return_data.id
                output[f'{self.name}_container_id'] = self.container_id
                print('container id is ' + self.container_id)
                return output, 'running'

            else:
                # return_data will be the bytes returned from the command
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
            logger.error('Could not get container!')
            return None

    def get_output(self) -> Tuple[str, str]:
        if not self.detach:
            return '', 'success'

        try:
            container = self.get_container()
            if container.status == 'running':
                return container.logs(), 'running'
            else:
                return container.logs(), 'success'

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
                container.remove()
        except APIError as ae:
            raise SkilletLoaderException(f'Could not clean up {self.name}: {ae}')
