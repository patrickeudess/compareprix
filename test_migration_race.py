"""Tests : démarrage simultané de plusieurs processus sur une base à migrer (schema_util, collaboration, verification).
Régression : « duplicate column name » faisait planter un worker au démarrage, par exemple au premier déploiement
après l'ajout d'une colonne. Lancer : python -m unittest test_migration_race -v"""
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

import schema_util

ROOT = os.path.dirname(os.path.abspath(__file__))
OLD_SCHEMA = '''
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE contributions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), article TEXT NOT NULL,
  brand TEXT NOT NULL, variant TEXT NOT NULL, quantity REAL NOT NULL, unit TEXT NOT NULL, price INTEGER NOT NULL,
  store TEXT NOT NULL, location TEXT NOT NULL, observed_at TEXT NOT NULL, created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', proof TEXT, proof_hash TEXT UNIQUE, fingerprint TEXT UNIQUE NOT NULL,
  review_note TEXT NOT NULL DEFAULT '', reviewed_at TEXT);
INSERT INTO users VALUES (1, 'phone:+2250102030405', 'Awa', 'x', '2026-01-01');
'''
CHILD = '''
import os, sys, time
sys.path.insert(0, %r); os.chdir(%r)
while time.time() < float(sys.argv[1]): pass
from flask import Flask
from collaboration import register_collaboration
register_collaboration(Flask(__name__), lambda: False)
''' % (ROOT, ROOT)


class FakeRacingConnection:
    """Simule le second processus : la colonne paraît absente, mais l'autre vient de l'ajouter."""

    def __init__(self, error):
        self.error, self.statements = error, []

    def execute(self, sql, *args):
        self.statements.append(sql)
        if sql.startswith('PRAGMA'):
            return iter([(0, 'id'), (1, 'name')])  # pas de colonne « phone » visible
        raise self.error


class TestAddColumn(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE t (id INTEGER)')

    def test_adds_a_missing_column_once_and_reports_it(self):
        self.assertTrue(schema_util.add_column_if_missing(self.conn, 't', 'phone', 'TEXT'))
        self.assertFalse(schema_util.add_column_if_missing(self.conn, 't', 'phone', 'TEXT'))
        self.assertIn('phone', [row[1] for row in self.conn.execute('PRAGMA table_info(t)')])

    def test_default_value_applies_to_existing_rows(self):
        self.conn.execute('INSERT INTO t VALUES (1)')
        schema_util.add_column_if_missing(self.conn, 't', 'version', 'INTEGER NOT NULL DEFAULT 0')
        self.assertEqual(self.conn.execute('SELECT version FROM t').fetchone()[0], 0)

    def test_losing_the_race_is_tolerated(self):
        fake = FakeRacingConnection(sqlite3.OperationalError('duplicate column name: phone'))
        self.assertFalse(schema_util.add_column_if_missing(fake, 't', 'phone', 'TEXT'))  # pas d'exception

    def test_any_other_database_error_is_still_raised(self):
        for message in ('database is locked', 'no such table: t', 'disk I/O error'):
            fake = FakeRacingConnection(sqlite3.OperationalError(message))
            with self.assertRaises(sqlite3.OperationalError, msg=message):
                schema_util.add_column_if_missing(fake, 't', 'phone', 'TEXT')


class TestSimultaneousStartup(unittest.TestCase):
    PROCESSES, TRIALS = 4, 8

    def run_trial(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(__import__('shutil').rmtree, folder, True)
        conn = sqlite3.connect(os.path.join(folder, 'community.sqlite3'))
        conn.executescript(OLD_SCHEMA)
        conn.commit()
        conn.close()
        env = {**os.environ, 'COMPAREPRIX_DATA_DIR': folder, 'COMPAREPRIX_SECRET_KEY': 'cle-de-test'}
        start = str(time.time() + 0.8)
        procs = [subprocess.Popen([sys.executable, '-c', CHILD, start], env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(self.PROCESSES)]
        results = [(p.wait(), p.stderr.read()) for p in procs]
        for p in procs:
            p.stdout.close()
            p.stderr.close()
        return folder, [stderr.strip().splitlines()[-1] for code, stderr in results if code != 0]

    def test_four_processes_starting_together_never_crash_and_migrate_everything(self):
        for _ in range(self.TRIALS):
            folder, failures = self.run_trial()
            self.assertEqual(failures, [])
        conn = sqlite3.connect(os.path.join(folder, 'community.sqlite3'))
        self.addCleanup(conn.close)
        users = {row[1] for row in conn.execute('PRAGMA table_info(users)')}
        self.assertTrue({'phone', 'session_version', 'consent_at', 'contact_email', 'email_verified_at'} <= users, users)
        contributions = {row[1] for row in conn.execute('PRAGMA table_info(contributions)')}
        self.assertTrue({'availability', 'city', 'district', 'shop'} <= contributions, contributions)
        self.assertEqual(conn.execute('SELECT name FROM users WHERE id = 1').fetchone()[0], 'Awa')  # données conservées


if __name__ == '__main__':
    unittest.main()
