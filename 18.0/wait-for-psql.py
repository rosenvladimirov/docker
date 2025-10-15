#!/usr/bin/env python3
import argparse
import psycopg2
import sys
import time

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--db_host', required=True)
    arg_parser.add_argument('--db_port', required=True)
    arg_parser.add_argument('--db_user', required=True)
    arg_parser.add_argument('--db_password', required=True)
    arg_parser.add_argument('--timeout', type=int, default=30)

    args = arg_parser.parse_args()

    start_time = time.time()
    error = None
    conn = None

    print(f"Waiting for PostgreSQL at {args.db_host}:{args.db_port}...")

    while (time.time() - start_time) < args.timeout:
        try:
            conn = psycopg2.connect(
                user=args.db_user,
                host=args.db_host,
                port=args.db_port,
                password=args.db_password,
                dbname='postgres',
                connect_timeout=5
            )
            print(f"✓ Successfully connected to PostgreSQL at {args.db_host}:{args.db_port}")
            conn.close()
            sys.exit(0)
        except psycopg2.OperationalError as e:
            error = e
            elapsed = int(time.time() - start_time)
            print(f"Attempt failed ({elapsed}s/{args.timeout}s): {error}")
            time.sleep(2)
        except Exception as e:
            error = e
            print(f"Unexpected error: {error}", file=sys.stderr)
            time.sleep(2)

    print(f"✗ Database connection failure after {args.timeout}s: {error}", file=sys.stderr)
    sys.exit(1)