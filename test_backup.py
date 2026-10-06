"""Tests de la sauvegarde SQLite. Lancer : python -m unittest test_backup -v"""
import os
import sqlite3
import tempfile
import unittest

import backup_db
import db


class TestBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, 'live.db')
        os.environ['COMPAREPRIX_DB'] = self.src
        db.init_db(seed=False)
        with db.transaction() as c:
            db.add_observation(c, {'article': 'Riz', 'supermarche': 'A', 'prix': 500, 'unite': 'kg',
                                   'date_releve': '2025-06-10', 'source': 'manuel', 'statut': 'valide'})
        self.dest = os.path.join(self.tmp.name, 'bk')

    def test_backup_is_a_complete_usable_copy(self):
        path = backup_db.create_backup(self.dest)
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute('SELECT prix FROM price_observation').fetchone()[0], 500)
        self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_rotation_keeps_newest_and_never_touches_other_files(self):
        os.makedirs(self.dest)
        foreign = os.path.join(self.dest, 'notes.txt')
        open(foreign, 'w').close()
        paths = [backup_db.create_backup(self.dest, keep=3) for _ in range(5)]
        left = sorted(f for f in os.listdir(self.dest) if f.endswith('.db'))
        self.assertEqual(len(left), 3)
        self.assertEqual(left, sorted(os.path.basename(p) for p in paths[-3:]))
        self.assertTrue(os.path.exists(foreign))

    def test_missing_source_raises(self):
        with self.assertRaises(FileNotFoundError):
            backup_db.create_backup(self.dest, source=os.path.join(self.tmp.name, 'nope.db'))

    def test_corrupt_source_fails_and_leaves_no_file(self):
        bad = os.path.join(self.tmp.name, 'bad.db')
        with open(bad, 'wb') as f:
            f.write(b'ceci n est pas une base sqlite' * 100)
        with self.assertRaises(sqlite3.Error):
            backup_db.create_backup(self.dest, source=bad)
        self.assertEqual([f for f in os.listdir(self.dest) if f.endswith('.db')], [])  # aucun fichier partiel


if __name__ == '__main__':
    unittest.main()
