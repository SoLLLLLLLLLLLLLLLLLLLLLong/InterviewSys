"""Run the legacy SQLite/JSON migration against the configured platform database.

The migration implementation is database-neutral because it writes through
SQLAlchemy. This entry point avoids tying the command name to PostgreSQL.
"""

from migrate_local_to_postgres import main


if __name__ == "__main__":
    main()
