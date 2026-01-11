"""
Command-line interface for PySFT.

Provides CLI access to financial data fetching and database management.
"""

import argparse
import sys
from pathlib import Path

from pysft.core import constants


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PySFT - Python Securities Fetching Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Database options
    db_group = parser.add_argument_group('Database Options')
    db_group.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable database caching and always fetch fresh data from web'
    )
    db_group.add_argument(
        '--cache-db',
        type=str,
        metavar='PATH',
        help=f'Path to cache database file (default: {constants.DB_PATH})'
    )
    
    # Version info
    parser.add_argument(
        '--version',
        action='version',
        version=f'PySFT {getattr(constants, "PACKAGE_VERSION", "dev")}'
    )
    
    args = parser.parse_args()
    
    # Apply CLI options to constants
    if args.no_cache:
        constants.DB_ENABLED = False
        print("Database caching disabled")
    
    if args.cache_db:
        cache_path = Path(args.cache_db)
        constants.DB_PATH = str(cache_path.absolute())
        print(f"Using cache database: {constants.DB_PATH}")
    
    # For now, just show configuration
    print("PySFT package installed.")
    print(f"Cache enabled: {constants.DB_ENABLED}")
    print(f"Cache database: {constants.DB_PATH}")
    print("\nCLI functionality to be expanded.")
    print("Use the Python API: from pysft.lib.fetchFinancialData import fetchData")


if __name__ == "__main__":
    main()

