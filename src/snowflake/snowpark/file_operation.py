#
# Copyright (c) 2012-2021 Snowflake Computing Inc. All rights reserved.
#
import os
from collections import UserDict
from typing import Dict, List, Optional, Union

import snowflake.snowpark
from snowflake.snowpark._internal.utils import Utils


class PutResult(UserDict):
    """Represents the results of uploading a local file to a stage location."""

    def __init__(self, data: Dict[str, Union[str, int]]):
        super(PutResult, self).__init__(data)

    @property
    def source(self) -> str:
        """The source file path."""
        return self.get("source")

    @property
    def target(self) -> str:
        """The file path in the stage where the source file is uploaded."""
        return self.get("target")

    @property
    def source_size(self) -> int:
        """The size in bytes of the source file."""
        return self.get("source_size")

    @property
    def target_size(self) -> int:
        """The size in bytes of the uploaded file in the stage."""
        return self.get("target_size")

    @property
    def source_compression(self) -> str:
        """The source file compression format."""
        return self.get("source_compression")

    @property
    def target_compression(self) -> str:
        """The target file compression format."""
        return self.get("target_compression")

    @property
    def status(self) -> str:
        """Status indicating whether the file was uploaded to the stage.
        Values can be 'UPLOADED' or 'SKIPPED'.
        """
        return self.get("status")

    @property
    def message(self) -> str:
        """The detailed message of the upload status."""
        return self.get("message")


class GetResult(UserDict):
    """Represents the results of downloading a file from a stage location to the local file system."""

    def __init__(self, data: Dict[str, Union[str, int]]):
        super(GetResult, self).__init__(data)

    @property
    def file(self) -> str:
        """Downloaded file path."""
        return self.get("file")

    @property
    def size(self) -> int:
        """Size in bytes of the downloaded file."""
        return self.get("size")

    @property
    def status(self) -> str:
        """Indicates whether the download is successful."""
        return self.get("status")

    @property
    def message(self) -> str:
        """Detailed message about the download status."""
        return self.get("message")


class FileOperation:
    """Provides methods for working on files in a stage.
    To access an object of this class, use :meth:`Session.file`.

    Examples::

        # Upload a file to a stage.
        session.file.put("file:///tmp/file1.csv", "@myStage/prefix1")
        # Download a file from a stage.
        session.file.get("@myStage/prefix1/file1.csv", "file:///tmp")
    """

    def __init__(self, session: "snowflake.snowpark.Session"):
        self._session = session

    def put(
        self,
        local_file_name: str,
        stage_location: str,
        *,
        parallel: int = 4,
        auto_compress: bool = True,
        source_compression: str = "AUTO_DETECT",
        overwrite: bool = False,
    ) -> List[PutResult]:
        """Uploads local files to the stage.

        References: `Snowflake PUT command <https://docs.snowflake.com/en/sql-reference/sql/put.html>`_.

        Example::

            put_result = session.file.put("/tmp/file*.csv", "@myStage/prefix2", auto_compress=False)

        Args:
            local_file_name: The path to the local files to upload. To match multiple files in the path,
                you can specify the wildcard characters ``*`` and ``?``.
            stage_location: The stage and prefix where you want to upload the files.
            parallel: Specifies the number of threads to use for uploading files. The upload process separates batches of data files by size:

                  - Small files (< 64 MB compressed or uncompressed) are staged in parallel as individual files.
                  - Larger files are automatically split into chunks, staged concurrently, and reassembled in the target stage. A single thread can upload multiple chunks.

                Increasing the number of threads can improve performance when uploading large files.
                Supported values: Any integer value from 1 (no parallelism) to 99 (use 99 threads for uploading files).
            auto_compress: Specifies whether Snowflake uses gzip to compress files during upload.
            source_compression: Specifies the method of compression used on already-compressed files that are being staged.
                Values can be 'AUTO_DETECT', 'GZIP', 'BZ2', 'BROTLI', 'ZSTD', 'DEFLATE', 'RAW_DEFLATE', 'NONE'.
            overwrite: Specifies whether Snowflake will overwrite an existing file with the same name during upload.

        Returns:
            A ``list`` of :class:`PutResult` instances, each of which represents the results of an uploaded file.
        """
        options = {
            "parallel": parallel,
            "source_compression": source_compression,
            "auto_compress": auto_compress,
            "overwrite": overwrite,
        }
        plan = self._session._Session__plan_builder.file_operation_plan(
            "put",
            Utils.normalize_local_file(local_file_name),
            Utils.normalize_stage_location(stage_location),
            options,
        )
        put_result = snowflake.snowpark.DataFrame(self._session, plan).collect()
        return [PutResult(file_result.asDict()) for file_result in put_result]

    def get(
        self,
        stage_location: str,
        target_directory: str,
        *,
        parallel: int = 10,
        pattern: Optional[str] = None,
    ) -> List[GetResult]:
        """Downloads the specified files from a path in a stage to a local directory.

        References: `Snowflake GET command <https://docs.snowflake.com/en/sql-reference/sql/get.html>`_.

        Examples::

            # Upload files to a stage.
            session.file.put("/tmp/file_1.csv", "@myStage/prefix")
            session.file.put("/tmp/file_2.csv", "@myStage/prefix")

            # Download one file from a stage.
            get_result1 = session.file.get("@myStage/prefix/file_1.csv", "/tmp/target")

            # Download all the files from @myStage/prefix.
            get_result2 = session.file.get("@myStage/prefix", "/tmp/target2")

            # Download files with names that match a regular expression pattern.
            get_result3 = session.file.get("@myStage/prefix", "/tmp/target3", pattern=".*file_.*.csv.gz")

        Args:
            stage_location: A directory or filename on a stage, from which you want to download the files.
            target_directory: The path to the local directory where the files should be downloaded.
                If ``target_directory`` does not already exist, the method creates the directory.
            parallel: Specifies the number of threads to use for downloading the files.
                The granularity unit for downloading is one file.
                Increasing the number of threads might improve performance when downloading large files.
                Supported values: Any integer value from 1 (no parallelism) to 99 (use 99 threads for downloading files).
            pattern: Specifies a regular expression pattern for filtering files to download.
                The command lists all files in the specified path and applies the regular expression pattern on each of the files found.
                Default: ``None`` (all files in the specified stage are downloaded).

        Returns:
            A ``list`` of :class:`GetResult` instances, each of which represents the result of a downloaded file.

        """
        options = {"parallel": parallel}
        if pattern is not None:
            options["pattern"] = (
                pattern if Utils.is_single_quoted(pattern) else f"'{pattern}'"
            )  # snowflake pattern is a string with single quote
        plan = self._session._Session__plan_builder.file_operation_plan(
            "get",
            Utils.normalize_local_file(target_directory),
            Utils.normalize_stage_location(stage_location),
            options,
        )
        try:
            # JDBC auto-creates directory but python-connector doesn't. So create the folder here.
            os.makedirs(Utils.get_local_file_path(target_directory), exist_ok=True)
            get_result = snowflake.snowpark.DataFrame(self._session, plan).collect()
            return [GetResult(file_result.asDict()) for file_result in get_result]
        # connector raises IndexError when no file is downloaded from python connector.
        # TODO: https://snowflakecomputing.atlassian.net/browse/SNOW-499333. Discuss with python connector whether
        #  we need to raise a different error.
        except IndexError:
            return []