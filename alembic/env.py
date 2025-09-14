import os
import sys
import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, MetaData
from sqlalchemy import pool

from alembic import context

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Lightweight imports - avoid full Flask app initialization
from db_base import Base  # Just get the Base class

# Setup logging for migration operations
logger = logging.getLogger('alembic.runtime.migration')

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use Base metadata directly to avoid app initialization
target_metadata = Base.metadata

# Import models to register them with SQLAlchemy - but do this after setting target_metadata
# to avoid full app initialization
try:
    import models  # Import models to register them with SQLAlchemy
    import models_pca  # Import PCA models too
except ImportError as e:
    print(f"Warning: Could not import models: {e}")
    pass

# Configuration for concurrent operations
def needs_concurrent_operations() -> bool:
    """
    Check if the current migration requires concurrent operations.
    
    This can be determined by (in order of precedence):
    1. Environment variable CONCURRENT_MIGRATION=true (global override)
    2. Per-script hook: revision script defining requires_concurrent_operations() function
    3. Migration file containing 'CONCURRENT' in name or content
    4. Command line revision containing 'concurrent'
    
    Returns:
        bool: True if concurrent operations are needed
    """
    # Check environment variable first (global override)
    if os.environ.get('CONCURRENT_MIGRATION', '').lower() == 'true':
        logger.info("✓ Concurrent operations enabled via CONCURRENT_MIGRATION env var")
        return True
    
    # Check per-script hook: import current revision and check for requires_concurrent_operations()
    try:
        # Get the current revision being processed
        script_directory = context.script
        if script_directory:
            # Get head revision or specific revision being processed
            heads = script_directory.get_heads()
            if heads:
                for head in heads:
                    revision_script = script_directory.get_revision(head)
                    if revision_script and revision_script.module:
                        # Check if the revision module defines requires_concurrent_operations()
                        if hasattr(revision_script.module, 'requires_concurrent_operations'):
                            requires_concurrent = revision_script.module.requires_concurrent_operations()
                            if requires_concurrent:
                                logger.info(f"✓ Concurrent operations required by revision {head} hook")
                                return True
                            else:
                                logger.info(f"✓ Revision {head} explicitly disables concurrent operations")
    except Exception as e:
        logger.debug(f"Could not check per-script hooks: {e}")
        pass  # Safe to ignore if we can't determine revision hooks
    
    # Check if current migration revision indicates concurrent operations (legacy)
    try:
        revision = context.get_revision_argument()
        if revision:
            # Handle case where revision might be a tuple or string
            revision_str = revision[0] if isinstance(revision, tuple) else str(revision)
            if 'concurrent' in revision_str.lower():
                logger.info(f"✓ Concurrent operations detected in revision name: {revision_str}")
                return True
    except Exception as e:
        logger.debug(f"Could not check revision argument: {e}")
        pass  # Safe to ignore if we can't determine revision
    
    logger.debug("No concurrent operation indicators found - using transactional mode")
    return False

def configure_for_concurrent():
    """
    Configure Alembic context for concurrent operations.
    
    This disables transactions and sets up proper isolation
    for CREATE INDEX CONCURRENTLY and similar operations.
    """
    logger.info("Configuring Alembic for concurrent operations")
    logger.info("⚠ Transactions disabled for concurrent DDL operations")
    
    # Import migration helpers when needed
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.migrations import configure_alembic_for_concurrent
        configure_alembic_for_concurrent()
    except ImportError as e:
        logger.warning(f"Could not import migration helpers: {e}")

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Get database URL from environment variable
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise ValueError("DATABASE_URL environment variable is required")
        
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    
    Supports both transactional and concurrent (non-transactional) operations.
    """
    # Get database URL from environment variable
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    
    # Set the database URL in config for engine creation
    config.set_main_option('sqlalchemy.url', database_url)
    
    # Check if we need concurrent operations
    concurrent_mode = needs_concurrent_operations()
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if concurrent_mode:
            # Configure for concurrent operations (no transactions)
            logger.info("🔧 Running migrations in CONCURRENT mode")
            configure_for_concurrent()
            
            # Set AUTOCOMMIT isolation level for concurrent operations (replaces deprecated autocommit=True)
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                transaction_per_migration=False,  # Critical for concurrent operations
                transactional_ddl=False,  # Disable DDL transactions for concurrent operations
                render_as_batch=False,  # Prevent batch operation wrapping
                compare_type=True,
                compare_server_default=True
            )
            
            # Run migrations without transaction wrapper
            context.run_migrations()
            logger.info("✅ Concurrent migrations completed")
            
        else:
            # Standard transactional mode
            logger.info("🔧 Running migrations in TRANSACTIONAL mode")
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True
            )

            with context.begin_transaction():
                context.run_migrations()
            logger.info("✅ Transactional migrations completed")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
