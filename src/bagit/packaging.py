"""
Packaging support for BagIt bags.

This module contains archive-related functionality that depends on
optional or heavyweight standard-library modules such as:

- tarfile
- zipfile
- zipstream-ng (optional)

Keeping packaging logic separate from the core Bag implementation
reduces dependencies and improves maintainability.
"""

import os


class BagPackager:
    """
    Helper class responsible for packaging BagIt bags into archive formats.

    This class provides support for:

        - TAR archives
        - TAR streams
        - ZIP archives
        - ZIP streams (optional dependency)

    The class is intentionally separated from :class: `Bag`to keep archive
    dependencies isolated from the core BagIt implementation.

    Parameters
    ----------
    bag : Bag
        The bag to package.
    """

    def __init__(self, bag):
        self.bag = bag

    def _iter_files(self):
        """
        Iterate over all files contained in the bag.

        Yield
        -----
        tuple[str, str]
           A tuple containing:

           - the filesystem path of the file
           - the archive path to use inside the generated archive

        Notes
        -----
        Files are yielded in deterministic order to improve reproducbility
        """

        for dirpath, _, filenames in os.walk(self.bag.path):
            filenames.sort()
            for filename in filenames:
                fpath = os.path.join(dirpath, filename)
                arcname = os.path.join(
                    os.path.basename(self.bag.path),
                    os.path.relpath(fpath, self.bag.path),
                )
                yield fpath, arcname

    def package_as_tar(self, tarpath, compression="gz"):
        """
        Write the bag to a TAR archive.

        Parameters
        ----------
        tarptath : str
           Destination TAR file.

        compression: : {None, "gz", "bz2", "xz"}
           Compression algorithm

        Notes
        -----
        The resulting archive contains the bag directory itself as the
        archive root.
        """
        import tarfile

        if compression not in (None, "gz", "bz2", "xz"):
            raise ValueError("compression must be one of None, 'gz', 'bz2', or 'xz'")

        mode = "w:%s" % compression if compression else "w"

        with tarfile.open(tarpath, mode) as tar:
            tar.add(self.bag.path, arcname=os.path.basename(self.bag.path))

    def package_as_tarstream(self, fobj, compression=None):
        """
        Stream the bag as a TAR archive.

        Parameters
        ----------
        fobj : file-like object
            Binary file object receiving TAR data.

        compression : {None, "gz", "bz2", "xz"}
            Optional compression algorithm.

        Notes
        -----
        This method is intended for network transfers or situations where
        a temporary archive file should not be created.
        """
        import tarfile

        if compression not in (None, "gz", "bz2", "xz"):
            raise ValueError("compression must be one of None, 'gz', 'bz2', or 'xz'")

        mode = "w|%s" % compression if compression else "w|"

        with tarfile.open(fileobj=fobj, mode=mode) as tar:
            tar.add(self.bag.path, arcname=os.path.basename(self.bag.path))

    def package_as_zip(self, zippath, compression="deflate"):
        """
        Write the bag to a ZIP archive.

        Parameters
        ----------
        zippath : str
            Destination ZIP file.

        compression : {None, "store", "deflate"}
            ZIP compression method.
        """
        import zipfile

        compressions = {
            None: zipfile.ZIP_STORED,
            "store": zipfile.ZIP_STORED,
            "deflate": zipfile.ZIP_DEFLATED,
        }

        if compression not in compressions:
            raise ValueError("compression must be one of None, 'store', or 'deflate'")

        with zipfile.ZipFile(zippath, "w", compression=compressions[compression]) as zf:
            for fpath, arcname in self._iter_files():
                zf.write(fpath, arcname)

    def package_as_zipstream(self, compression="deflate"):
        """
        Create a streaming ZIP archive generator.

        Parameters
        ----------
        compression : {None, "store", "deflate"}
            ZIP compression method.

        Returns
        -------
        zipstream.ZipStream
            Iterable object producing ZIP archive chunks.

        Raises
        ------
        RuntimeError
            If the optional ``zipstream-ng`` dependency is not installed.

        Notes
        -----
        This feature requires the optional ``zipstream-ng`` package and is
        primarily intended for HTTP downloads and other streaming use cases.
        """
        try:
            import zipstream

            zipstream_cls = zipstream.ZipStream
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                "package_as_zipstream() requires the optional zipstream-ng dependency"
            ) from exc

        if compression in (None, "store"):
            zip_compression = zipstream.ZIP_STORED
        elif compression in ("deflate", "gz"):
            zip_compression = zipstream.ZIP_DEFLATED
        else:
            raise ValueError("compression must be one of None, 'store', or 'deflate'")

        zstream = zipstream_cls(compress_type=zip_compression)

        for fpath, arcname in self._iter_files():
            zstream.add_path(fpath, arcname)

        return zstream
