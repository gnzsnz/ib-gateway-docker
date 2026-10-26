from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional

import pandas as pd
import psycopg2

# ============================================================================
# Connection configuration
# ============================================================================

@dataclass
class PostgresConfig:
    """
    Configuration for connecting to PostgreSQL.
    """
    host: str = ""
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""

    @classmethod
    def from_env(cls, env_path: str = "/tmp/secrets/.env") -> PostgresConfig:
        """
        Create a config from a .env file (falls back to os.environ if key not found).
        """
        from dotenv import dotenv_values
        config = dotenv_values(env_path)
        return cls(
            host=config.get("POSTGRES_HOST"),
            port=int(config.get("POSTGRES_PORT")),
            database=config.get("POSTGRES_DATABASE"),
            username=config.get("POSTGRES_USERNAME"),
            password=config.get("POSTGRES_PASSWORD"),
        )


# ============================================================================
# Connection manager 
# ============================================================================

class PostgresConnection:
    """
    PostgreSQL connection manager.   
    """
    
    def __init__(self, config: PostgresConfig):
        """
        Initialize with configuration.
        
        Args:
            config: The PostgreSQL configuration
        """
        self.config = config
    
    def db_connect(self) -> psycopg2.extensions.connection:
        """
        Create a new connection to the database.
        
        Returns a psycopg2 connection object.
        """
        return psycopg2.connect(
            dbname=self.config.database,
            user=self.config.username,
            password=self.config.password,
            host=self.config.host,
            port=self.config.port
        )
    
    def select_from_query(self, query: str, params: tuple = ()) -> pd.DataFrame:
        """
        Execute a SELECT query and return results as a DataFrame.
        
        Args:
            query: SQL SELECT query with %s placeholders for parameters
            params: Tuple of parameter values
        
        Returns:
            DataFrame with query results
        """
        import warnings
        
        conn = self.db_connect()
        
        try:
            # Suppress pandas warning about DBAPI2 (psycopg2 works fine)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
                df = pd.read_sql(query, conn, params=params or None)
        finally:
            conn.close()
        
        return df

    def execute_write_querry(self, query: str, params: tuple = ()) -> None:
        """
        Execute a write query (INSERT, UPDATE, DELETE) with commit.
        
        Args:
            query: SQL query with %s placeholders for parameters
            params: Tuple of parameter values
        """
        conn = self.db_connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
        finally:
            conn.close()

    def test_connection(self) -> bool:
        """
        Test if the database connection works.
        
        Returns True if connection is OK, False otherwise.
        """
        try:
            conn = self.db_connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception as e:
            print(f"PostgreSQL connection error: {e}")
            return False




_global_connection: Optional[PostgresConnection] = None


def init_postgres(config: Optional[PostgresConfig] = None) -> PostgresConnection:
    """
    Initialize the global PostgreSQL connection.
    
    Args:
        config: The configuration. If None, uses environment variables.
    
    Returns:
        The PostgreSQL connection instance.
    """
    global _global_connection
    
    if config is None:
        config = PostgresConfig.from_env()
    
    _global_connection = PostgresConnection(config)
    return _global_connection


def get_postgres() -> PostgresConnection:
    """
    Get the global PostgreSQL connection.
    
    Raises:
        RuntimeError: If init_postgres() was not called before.
    """
    if _global_connection is None:
        raise RuntimeError(
            "PostgreSQL not initialized. "
            "Call init_postgres(config) first."
        )
    return _global_connection
