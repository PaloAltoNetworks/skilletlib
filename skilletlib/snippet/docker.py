import logging
from typing import Tuple

from docker import DockerClient
from docker.errors import APIError
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

        self.cmd = self.metadata.get('cmd', 'echo "you forgot a cmd silly')
        self.working_dir = self.metadata.get('working_dir', '/app')
        self.path = self.metadata.get('skillet_path')
        # set up volumes
        self.volumes = {self.path: {'bind': self.working_dir, 'mode': 'rw'}}

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
            container = self.client.containers.run(image, self.cmd, volumes=vols,
                                                   detach=True, working_dir=self.working_dir,
                                                   auto_remove=False, environment=context)

            self.container_id = container.id
            output[f'{self.name}_container_id'] = self.container_id
            print('container id is ' + self.container_id)
            return output, 'running'
        except ImageNotFound:
            raise SkilletLoaderException(f'Could not locate image {self.image} in {self.name}')
        except DockerException as de:
            raise SkilletLoaderException(f'Could not execute docker container {self.name}: {de}')

    def get_container(self):
        try:
            return self.client.containers.get(self.container_id)
        except DockerException as de:
            logger.error('Could not get container!')
            return None

    def get_output(self) -> Tuple[str, str]:
        try:
            container = self.get_container()
            if container.status == 'running':
                return container.logs(), 'running'
            else:
                return container.logs(), 'success'

        except APIError as ae:
            raise SkilletLoaderException(f'Could not get logs for {self.name}: {ae}')

    def cleanup(self):
        try:
            container = self.get_container()
            if container:
                container.remove()
        except APIError as ae:
            raise SkilletLoaderException(f'Could not clean up {self.name}: {ae}')
