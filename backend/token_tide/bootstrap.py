from token_tide.bookstore import Bookstore, StorageEngineFactory
from token_tide.config import Settings, get_settings

REMOTE_CONFIGURATION = "token-tide/application-:tail.yaml"
BOOKSTORE_TIMEOUT_MILLISECONDS = 8000


def bootstrap_settings() -> Settings:
    bookstore = Bookstore(StorageEngineFactory.new_storage_engine())
    bookstore.download_configuration(
        REMOTE_CONFIGURATION,
        BOOKSTORE_TIMEOUT_MILLISECONDS,
    )
    get_settings.cache_clear()
    return get_settings()
