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


class TestFullBackup(unittest.TestCase):
    """Régression : seule la base des prix était sauvegardée ; comptes, contributions, points et photos étaient perdus
    en cas de panne du disque."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = os.path.join(self.tmp.name, 'data')
        os.makedirs(os.path.join(self.folder, 'proofs'))
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.folder, 'compareprix.db')
        db.init_db(seed=False)
        with db.transaction() as c:
            db.add_observation(c, {'article': 'Riz', 'supermarche': 'A', 'prix': 500, 'unite': 'kg',
                                   'date_releve': '2025-06-10', 'source': 'manuel', 'statut': 'valide'})
        conn = sqlite3.connect(os.path.join(self.folder, 'community.sqlite3'))
        conn.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"
                           "INSERT INTO users VALUES (1,'Awa'),(2,'Koffi');"
                           "CREATE TABLE contributions (id INTEGER PRIMARY KEY, article TEXT);"
                           "INSERT INTO contributions VALUES (1,'Riz');")
        conn.commit()
        conn.close()
        self.dest = os.path.join(self.tmp.name, 'bk')
        self.write_proof('a.jpg', b'photo-a')

    def write_proof(self, name, content):
        with open(os.path.join(self.folder, 'proofs', name), 'wb') as f:
            f.write(content)

    def run_backup(self, **kw):
        return backup_db.create_full_backup(self.dest, folder=self.folder, **kw)

    def test_accounts_contributions_prices_and_photos_are_all_saved(self):
        report = self.run_backup()
        self.assertEqual(report['errors'], [])
        names = sorted(os.path.basename(p).split('_')[0] for p in report['files'])
        self.assertEqual(names, ['community', 'compareprix'])
        community = next(p for p in report['files'] if 'community_' in p)
        info = backup_db.describe_backup(community)
        self.assertEqual((info['integrity'], info['counts']), ('ok', {'users': 2, 'contributions': 1}))
        prices = backup_db.describe_backup(next(p for p in report['files'] if 'compareprix_' in p))
        self.assertEqual(prices['counts']['price_observation'], 1)
        with open(os.path.join(self.dest, 'proofs', 'a.jpg'), 'rb') as f:
            self.assertEqual(f.read(), b'photo-a')

    def test_a_restored_copy_is_a_working_database(self):
        report = self.run_backup()
        restored = os.path.join(self.tmp.name, 'restaure.sqlite3')
        __import__('shutil').copy(next(p for p in report['files'] if 'community_' in p), restored)
        conn = sqlite3.connect(restored)
        self.addCleanup(conn.close)
        conn.execute("INSERT INTO users VALUES (3, 'Nouvelle')")  # elle accepte de nouveau des écritures
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM users').fetchone()[0], 3)

    def test_photos_are_copied_incrementally_and_never_deleted(self):
        self.assertEqual(self.run_backup()['proofs_copied'], 1)
        second = self.run_backup()
        self.assertEqual((second['proofs_copied'], second['proofs_present']), (0, 1))
        self.write_proof('b.jpg', b'photo-b')
        third = self.run_backup()
        self.assertEqual((third['proofs_copied'], third['proofs_present']), (1, 1))
        os.remove(os.path.join(self.folder, 'proofs', 'a.jpg'))  # supprimée à la source : la sauvegarde la garde
        self.run_backup()
        self.assertTrue(os.path.exists(os.path.join(self.dest, 'proofs', 'a.jpg')))
        self.assertEqual([f for f in os.listdir(os.path.join(self.dest, 'proofs')) if f.endswith('.part')], [])

    def test_rotation_is_independent_for_each_kind(self):
        for _ in range(4):
            self.run_backup(keep=2)
        files = os.listdir(self.dest)
        self.assertEqual(len([f for f in files if f.startswith('community_')]), 2)
        self.assertEqual(len([f for f in files if f.startswith('compareprix_')]), 2)

    def test_a_corrupt_community_db_is_reported_but_does_not_stop_the_other_backups(self):
        with open(os.path.join(self.folder, 'community.sqlite3'), 'wb') as f:
            f.write(b'pas une base' * 200)
        report = self.run_backup()
        self.assertEqual(len(report['errors']), 1)
        self.assertIn('comptes', report['errors'][0])
        self.assertEqual(len(report['files']), 1)  # les prix sont sauvegardés quand même
        self.assertEqual(report['proofs_copied'], 1)
        self.assertEqual([f for f in os.listdir(self.dest) if f.startswith('community_')], [])  # aucun fichier partiel

    def test_fresh_install_without_community_db_is_not_an_error(self):
        os.remove(os.path.join(self.folder, 'community.sqlite3'))
        report = self.run_backup()
        self.assertEqual(report['errors'], [])
        self.assertTrue(any('comptes' in line for line in report['skipped']))

    @unittest.skipIf(os.name == 'nt', 'permissions POSIX')
    def test_backups_holding_personal_data_are_private(self):
        report = self.run_backup()
        self.assertEqual(os.stat(self.dest).st_mode & 0o777, 0o700)
        for path in report['files'] + [os.path.join(self.dest, 'proofs', 'a.jpg')]:
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600, path)

    def test_session_secret_is_never_copied(self):
        with open(os.path.join(self.folder, '.session-secret'), 'w') as f:
            f.write('secret')
        self.run_backup()
        for root, _, files in os.walk(self.dest):
            self.assertNotIn('.session-secret', files)

    def test_verify_reports_a_damaged_file(self):
        bad = os.path.join(self.tmp.name, 'abime.db')
        with open(bad, 'wb') as f:
            f.write(b'xxxxxxxxxxxxxxxx' * 500)
        with self.assertRaises(sqlite3.Error):
            backup_db.describe_backup(bad)


if __name__ == '__main__':
    unittest.main()
