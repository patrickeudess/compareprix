"""Tests : prix consultés en ligne (online_prices) et leur stockage SQLite (source 'prix_internet').
Lancer : python -m unittest test_online_prices -v"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import db
import online_prices
from pricing import enrich_results, freshness, normalize_article, validate_article

URL = 'https://www.jumia.ci/maman-riz-maman-5-kg-3315611.html'
ROW = {'article': 'Riz Maman', 'supermarche': 'Jumia CI (en ligne)', 'prix': 2820, 'unite': '5 kg', 'url': URL,
       'source': 'prix_internet', 'date_consultation': '2026-10-07', 'date_releve': None,
       'statut': 'prix_internet', 'disponibilite': 'unknown', 'prix_unitaire': 564, 'unite_reference': 'kg',
       'lieu': 'En ligne', 'source_catalogue': 'https://www.jumia.ci/epicerie/'}


def page(price='3000', currency='XOF', stock='InStock', offers=None):
    doc = {'@type': 'Product', 'offers': offers or {'@type': 'Offer', 'price': price, 'priceCurrency': currency,
                                                    'availability': 'https://schema.org/' + stock}}
    return ('<html><script type="application/ld+json">%s</script></html>' % json.dumps(doc)).encode()


class FakeResponse:
    def __init__(self, body, url=URL):
        self.body, self.url = body, url

    def read(self, _limit=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestPriceReading(unittest.TestCase):
    def read(self, body, url=URL, final=None):
        with mock.patch.object(online_prices, 'urlopen', return_value=FakeResponse(body, final or url)):
            return online_prices.read_price(url)

    def test_reads_a_single_xof_offer(self):
        r = self.read(page('3000'))
        self.assertEqual((r['prix'], r['disponibilite'], r['actualisation']), (3000, 'available', 'ok'))
        self.assertEqual(self.read(page(stock='OutOfStock'))['disponibilite'], 'out_of_stock')

    def test_rejects_unsupported_links_without_any_request(self):
        for bad in ('http://www.jumia.ci/x.html', 'https://evil.example/x.html', 'https://www.jumia.ci/epicerie/',
                    'https://user:pw@www.jumia.ci/x.html', 'https://www.jumia.ci.evil.example/x.html'):
            with mock.patch.object(online_prices, 'urlopen') as fake, self.assertRaises(ValueError):
                online_prices.read_price(bad)
            fake.assert_not_called()

    def test_never_infers_a_price(self):
        agg = {'@type': 'AggregateOffer', 'lowPrice': '1', 'priceCurrency': 'XOF'}
        for body in (page(currency='EUR'), page('12.5'), page('0'), page(offers=agg), b'<html>sans donnees</html>',
                     page(offers=[{'price': '1', 'priceCurrency': 'XOF'}, {'price': '2', 'priceCurrency': 'XOF'}])):
            with self.assertRaises(ValueError):
                self.read(body)

    def test_rejects_redirect_to_another_host(self):
        with self.assertRaises(ValueError):
            self.read(page(), final='https://evil.example/x.html')


class CacheCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(online_prices, 'DB', Path(tmp.name) / 'online.sqlite3')
        patcher.start()
        self.addCleanup(patcher.stop)
        # aucun thread d'arrière-plan réel : le rafraîchissement est testé via refresh()
        patcher = mock.patch.object(online_prices.threading, 'Thread')
        self.thread = patcher.start()
        self.addCleanup(patcher.stop)


class TestApplyUpdates(CacheCase):
    def test_without_cache_rows_stay_pending_and_a_refresh_is_scheduled(self):
        rows = online_prices.apply_updates([dict(ROW)])
        self.assertEqual(rows[0]['actualisation'], 'pending')
        self.assertEqual(rows[0]['prix'], 2820)
        self.thread.assert_called_once()
        self.thread.return_value.start.assert_called_once()
        online_prices.WORKER_LOCK.release()  # le thread factice ne libère pas le verrou

    def test_other_sources_are_untouched(self):
        other = {'article': 'Lait', 'supermarche': 'Carrefour', 'prix': 500, 'source': 'manuel'}
        self.assertEqual(online_prices.apply_updates([dict(other)]), [other])
        self.thread.assert_not_called()

    def test_refresh_then_apply_rescales_the_unit_price(self):
        with mock.patch.object(online_prices, 'read_price', return_value={'prix': 3102, 'actualisation': 'ok',
                                                                         'disponibilite': 'available'}):
            online_prices.refresh([dict(ROW)])
        row = online_prices.apply_updates([dict(ROW)])[0]
        self.assertEqual((row['prix'], row['actualisation'], row['disponibilite']), (3102, 'ok', 'available'))
        self.assertAlmostEqual(row['prix_unitaire'], 564 * 3102 / 2820, places=2)
        self.thread.assert_not_called()  # cache frais (< 6 h) : pas de nouvelle consultation

    def test_failed_refresh_keeps_the_previous_price_and_says_so(self):
        with mock.patch.object(online_prices, 'read_price', side_effect=ValueError('boom')):
            online_prices.refresh([dict(ROW)])
        row = online_prices.apply_updates([dict(ROW)])[0]
        self.assertEqual((row['prix'], row['actualisation']), (2820, 'unavailable'))

    def test_refresh_ignores_rows_that_are_not_online_prices(self):
        with mock.patch.object(online_prices, 'read_price') as fake:
            online_prices.refresh([{'url': URL, 'source': 'manuel'}])
        fake.assert_not_called()


class TestStorage(unittest.TestCase):
    """'prix_internet' est une source valide du schéma ; ce n'est jamais une donnée d'exemple."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(tmp.name, 'p.db')
        db.init_db(seed=False)

    def test_online_price_roundtrip_keeps_its_provenance_fields(self):
        with db.transaction() as conn:
            _, created = db.add_observation(conn, dict(ROW))
        self.assertTrue(created)
        got = db.list_current('riz maman')[0]
        self.assertEqual((got['source'], got['statut']), ('prix_internet', 'a_verifier'))
        for key in ('date_consultation', 'disponibilite', 'prix_unitaire', 'unite_reference', 'lieu', 'source_catalogue', 'url'):
            self.assertEqual(got[key], ROW[key], key)
        with db.transaction() as conn:
            self.assertFalse(db.add_observation(conn, dict(ROW))[1])  # rejouable : pas de doublon

    def test_legacy_status_is_mapped_and_never_becomes_a_sample(self):
        a = normalize_article(ROW)
        self.assertEqual(a['statut'], 'a_verifier')
        self.assertEqual(freshness(a)[0], 'inconnue')
        self.assertIn('prix_internet', __import__('pricing').SOURCES)

    def test_catalogue_unit_price_survives_enrichment(self):
        e = enrich_results([dict(ROW, statut='a_verifier')])[0]
        self.assertEqual((e['prix_unitaire'], e['unite_base']), (564, 'kg'))

    def test_shipped_seed_file_loads_into_the_schema(self):
        stats = db.sync_from_json(feedback_path='/nonexistent', force=True)
        self.assertEqual(stats['observations'], 13)
        self.assertTrue(all(a['statut'] == 'a_verifier' and a['source'] == 'prix_internet' for a in db.list_current()))

    def test_admin_validation_still_rejects_unknown_sources(self):
        rec = dict(ROW, date_releve='2026-10-01', source='inconnue', statut='a_verifier')
        self.assertTrue(any('source' in e for e in validate_article(rec)))


if __name__ == '__main__':
    unittest.main()
