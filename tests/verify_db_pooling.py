import sqlite3
import threading
import time
from app.repositories.database_manager import DatabaseManager

def test_connection_pooling():
    db = DatabaseManager(pool_size=2) # Small pool for easy testing
    
    def worker(worker_id):
        print(f"Worker {worker_id} starting...")
        with db.connection_context() as conn:
            res = conn.execute("SELECT 1").fetchone()
            print(f"Worker {worker_id} got {res[0]} using connection {id(conn)}")
            # Check PRAGMA journal_mode
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            print(f"Worker {worker_id} journal mode: {mode}")
            time.sleep(0.5)
        print(f"Worker {worker_id} finished.")

    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("Created connections count:", db._created_connections)
    assert db._created_connections <= 2, f"Expected at most 2 connections, got {db._created_connections}"

if __name__ == "__main__":
    test_connection_pooling()
