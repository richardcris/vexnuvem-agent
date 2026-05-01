__all__ = ["__version__", "__github_repository__"]

_BASE_VERSION = "1.0.0"
_BASE_GITHUB_REPOSITORY = ""

try:
	from ._build_meta import BUILD_VERSION, GITHUB_REPOSITORY
except ImportError:
	BUILD_VERSION = _BASE_VERSION
	GITHUB_REPOSITORY = _BASE_GITHUB_REPOSITORY

__version__ = BUILD_VERSION or _BASE_VERSION
__github_repository__ = GITHUB_REPOSITORY or _BASE_GITHUB_REPOSITORY
