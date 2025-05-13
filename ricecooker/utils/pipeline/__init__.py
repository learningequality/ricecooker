import mimetypes
import os
from copy import deepcopy
from typing import Dict
from typing import Optional

from .convert import ConversionStageHandler
from .extract_metadata import ExtractMetadataStageHandler
from .file_handler import CompositeHandler
from .transfer import DownloadStageHandler
from ricecooker.utils.pipeline.context import FileMetadata


# Do this to prevent import of broken Windows filetype registry that makes guesstype not work.
# https://www.thecodingforums.com/threads/mimetypes-guess_type-broken-in-windows-on-py2-7-and-python-3-x.952693/
mimetypes.init([os.path.abspath(os.path.join(os.path.dirname(__file__), "mime.types"))])


class FilePipeline(CompositeHandler):
    """
    A class to manage a sequence of handlers and execute them in order.
    Each handler should be a subclass of Handler.
    The pipeline object will store global context that will be passed to each handler,
    but will be overridden by the context generated during the course of a file's processing.

    This pipeline can be customized by passing `children` as an argument to the constructor.

    For example to add a custom stage to the pipeline, you can do:
    ```python
    from ricecooker.utils.pipeline import FilePipeline
    from ricecooker.utils.pipeline.custom_stage import CustomStageHandler
    pipeline = FilePipeline(children=[CustomStageHandler()])
    ```

    To just modify one of the existing stages, you can do:
    ```python
    from ricecooker.utils.pipeline import FilePipeline
    from ricecooker.utils.pipeline.convert import ConversionStageHandler
    from ricecooker.utils.pipeline.extract_metadata import ExtractMetadataStageHandler
    from ricecooker.utils.pipeline.transfer import DownloadStageHandler
    from ricecooker.utils.pipeline.transfer import DiskResourceHandler

    download_stage = DownloadStageHandler(children=[DiskResourceHandler()])
    pipeline = FilePipeline(children=[download_stage, ConversionStageHandler(), ExtractMetadataStageHandler()])
    ```
    This will replace the default `DownloadStageHandler` with a new one that has a `DiskResourceHandler` as its only child.
    """

    DEFAULT_CHILDREN = [
        DownloadStageHandler,
        ConversionStageHandler,
        ExtractMetadataStageHandler,
    ]

    def execute(
        self,
        path: str,
        context: Optional[Dict] = None,
        skip_cache: Optional[bool] = False,
    ) -> list[FileMetadata]:
        """
        Execute the pipeline for a given file path.
        """
        context = context or {}
        file_metadata_list = [FileMetadata(path=path)]
        for handler in self._children:
            updated_file_metadata_list = []
            for file_metadata in file_metadata_list:
                if handler.should_handle(file_metadata.path):
                    # Pass in any context from the previous handler
                    scoped_context = deepcopy(context)
                    scoped_context.update(file_metadata.to_dict())
                    # Execute the handler and get the new list of metadata
                    new_metadata_list = handler.execute(
                        file_metadata.path,
                        context=scoped_context,
                        skip_cache=skip_cache,
                    )
                    for new_metadata in new_metadata_list:
                        # For each new metadata in the returned list
                        # make a unique copy of the existing metadata and
                        # merge the new metadata into the existing metadata
                        updated_file_metadata_list.append(
                            file_metadata.merge(new_metadata)
                        )
                else:
                    # Otherwise, it's a noop
                    updated_file_metadata_list.append(file_metadata)
            file_metadata_list = updated_file_metadata_list
        return file_metadata_list
