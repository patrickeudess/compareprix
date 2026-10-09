"""Tests : prix de référence nationaux (pricing.match_reference, db.list_references, import_references).
Lancer : python -m unittest test_references -v"""
import atexit
import io
import os
import tempfile
import unittest
from datetime import date, timedelta

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ.setdefault('COMPAREPRIX_DB', os.path.join(_TMP.name, 'boot.db'))

import db
import import_references as ir
import app as appmod
from pricing import attach_references, enrich_results, fold, match_reference

TODAY = date.today()
ISO = TODAY.isoformat()


def ref(**kw):
    base = dict(kind='plafond', label='Huile de palme raffinée 90 cl', include='huile', exclude='olive,coco',
                unit_base='L', qty_value=0.9, value=1200, zone='Abidjan', source_name='CNLVC',
                source_url='https://exemple.gouv.ci/plafonds', valid_from='2026-01-01', valid_to=None, verified=True)
    base.update(kw)
    return base


def art(name='Huile végétale 90 cl', prix=1150, **kw):
    base = dict(article=name, supermarche='Carrefour', prix=prix, unite='L', date_releve=ISO, source='manuel',
                statut='valide', ville='Abidjan')
    base.update(kw)
    return enrich_results([base])[0]


class TestMatching(unittest.TestCase):
    def test_fold_removes_accents_and_case(self):
        self.assertEqual(fold('  Huile  VÉGÉTALE '), 'huile vegetale')

    def test_include_words_whole_and_plural_tolerated(self):
        self.assertIsNotNone(match_reference(art('Huiles végétales 90cl'), [ref()]))
        self.assertIsNone(match_reference(art('Chuile 90cl'), [ref()]))

    def test_all_include_terms_required_and_exclude_blocks(self):
        r = ref(include='huile,palme')
        self.assertIsNone(match_reference(art('Huile végétale 90 cl'), [r]))
        self.assertIsNotNone(match_reference(art('Huile de palme 90 cl'), [r]))
        self.assertIsNone(match_reference(art("Huile d'olive 90 cl"), [ref()]))

    def test_ceiling_applies_only_to_the_exact_format(self):
        for name in ('Huile végétale 1L', 'Huile végétale 1,5 L', 'Huile végétale'):
            self.assertIsNone(match_reference(art(name), [ref()]), name)
        self.assertIsNotNone(match_reference(art('Huile végétale 90cl'), [ref()]))
        self.assertIsNotNone(match_reference(art('Huile Dinor', unite='90 cl'), [ref()]))  # format lu dans l'unité (Jumia)
        self.assertIsNone(match_reference(art('Huile 22,5 kg'), [ref()]))  # autre base d'unité

    def test_market_average_needs_a_unit_price_in_the_same_base(self):
        avg = ref(kind='moyenne_marche', include='plantain', exclude='', unit_base='kg', qty_value=None, value=500,
                  zone='', valid_to=ISO)
        self.assertIsNotNone(match_reference(art('Banane plantain 1kg', 600), [avg]))
        self.assertIsNone(match_reference(art('Banane plantain'), [avg]))  # pas de prix unitaire calculable
        self.assertIsNone(match_reference(art('Plantain 1L', 600, unite='L'), [avg]))

    def test_most_specific_then_most_recent_reference_wins(self):
        general = ref(label='général', include='huile', valid_from='2026-06-01')
        specific = ref(label='précis', include='huile,palme', valid_from='2026-01-01')
        self.assertEqual(match_reference(art('Huile de palme 90cl'), [general, specific])['label'], 'précis')
        newer = ref(label='récent', valid_from='2026-07-01')
        self.assertEqual(match_reference(art('Huile 90cl'), [ref(), newer])['label'], 'récent')


class TestVerdict(unittest.TestCase):
    def verdict(self, **kw):
        article = art(**kw)
        return attach_references([article], [ref()])[0]['reference']

    def test_above_and_conform_in_store_in_zone(self):
        self.assertEqual(self.verdict(prix=1300)['position'], 'above')
        self.assertEqual(self.verdict(prix=1300)['ecart_pct'], 8.3)
        self.assertEqual(self.verdict(prix=1200)['position'], 'conform')
        self.assertEqual(self.verdict(prix=900)['position'], 'conform')

    def test_no_verdict_for_online_prices_or_undated_or_other_zone(self):
        self.assertIsNone(self.verdict(prix=1300, source='prix_internet')['position'])
        self.assertIsNone(self.verdict(prix=1300, date_releve=None)['position'])
        self.assertIsNone(self.verdict(prix=1300, ville='Bouaké')['position'])
        self.assertIsNone(self.verdict(prix=1300, ville=None)['position'])  # zone inconnue : jamais de verdict

    def test_zone_can_come_from_the_place_text(self):
        self.assertEqual(self.verdict(prix=1300, ville=None, lieu='Abidjan · Cocody · Carrefour')['position'], 'above')

    def test_national_ceiling_without_zone_gives_a_verdict_in_store(self):
        article = art(prix=1300, ville=None)
        self.assertEqual(attach_references([article], [ref(zone='')])[0]['reference']['position'], 'above')

    def test_article_without_reference_gets_none(self):
        self.assertIsNone(attach_references([art('Savon 90cl')], [ref()])[0]['reference'])
        self.assertIsNone(attach_references([art()], [])[0]['reference'])


class RefDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.tmp.name, 'r.db')
        db.init_db(seed=False)

    def add(self, **kw):
        with db.transaction() as conn:
            return db.add_reference(conn, ref(**kw))


class TestStorage(RefDb):
    def test_unverified_expired_and_future_references_are_invisible(self):
        self.add(label='ok')
        self.add(label='non vérifiée', verified=False)
        self.add(label='expirée', valid_from='2025-01-01', valid_to=(TODAY - timedelta(days=1)).isoformat())
        self.add(label='future', valid_from=(TODAY + timedelta(days=1)).isoformat())
        self.assertEqual([r['label'] for r in db.list_references()], ['ok'])

    def test_validity_bounds_are_inclusive(self):
        self.add(label='dernier jour', valid_from='2026-01-01', valid_to=ISO)
        self.add(label='premier jour', valid_from=ISO)
        self.assertEqual({r['label'] for r in db.list_references()}, {'dernier jour', 'premier jour'})

    def test_same_reference_is_not_duplicated(self):
        self.assertTrue(self.add()[1])
        self.assertFalse(self.add()[1])
        self.assertTrue(self.add(value=1300, valid_from='2026-07-01')[1])  # nouvelle période = nouvelle ligne


class TestApi(RefDb):
    def setUp(self):
        super().setUp()
        with db.transaction() as conn:
            db.add_observation(conn, dict(article='Huile végétale 90 cl', supermarche='Carrefour', prix=1350, unite='L',
                                          date_releve=ISO, source='manuel', statut='valide', lieu='Abidjan · Cocody'))
        self.client = appmod.app.test_client()

    def rows(self):
        data = self.client.get('/api/articles').get_json()
        return [a for a in (data if isinstance(data, list) else data['articles']) if a['article'].startswith('Huile')]

    def test_no_reference_until_one_is_verified(self):
        self.add(verified=False)
        self.assertIsNone(self.rows()[0]['reference'])
        self.assertEqual(self.client.get('/api/references').get_json()['references'], [])

    def test_verified_reference_is_attached_with_source_and_verdict(self):
        self.add()
        reference = self.rows()[0]['reference']
        self.assertEqual((reference['position'], reference['source_name'], reference['value']), ('above', 'CNLVC', 1200))
        self.assertEqual(self.client.get('/api/references').get_json()['references'][0]['source_url'],
                         'https://exemple.gouv.ci/plafonds')


class TestImport(unittest.TestCase):
    HEADER = 'kind,label,include,exclude,unit_base,qty_value,value,zone,source_name,source_url,valid_from,valid_to,verified\n'

    def parse(self, *lines):
        return ir.parse_csv(io.StringIO(self.HEADER + '\n'.join(lines) + '\n'))

    OK = 'plafond,Huile 90 cl,huile,"olive,coco",L,"0,9","1 200 FCFA",Abidjan,CNLVC,https://exemple.gouv.ci/x,01/01/2026,,oui'

    def test_valid_row_with_french_formats(self):
        rows, errors, skipped = self.parse(self.OK)
        self.assertEqual(errors, [])
        self.assertEqual((rows[0]['value'], rows[0]['qty_value'], rows[0]['valid_from'], rows[0]['verified']),
                         (1200, 0.9, '2026-01-01', True))

    def test_blank_template_is_skipped_not_rejected(self):
        self.assertEqual(self.parse(), ([], [], 0))
        self.assertEqual(self.parse('plafond,Huile,huile,,L,0.9,,Abidjan,CNLVC,,2026-01-01,,non')[2], 1)

    def test_verified_needs_an_http_source(self):
        bad = self.OK.replace('https://exemple.gouv.ci/x', '')
        self.assertIn('source_url', ' '.join(self.parse(bad)[1][0][1]))
        self.assertEqual(self.parse(bad.replace(',oui', ',non'))[1], [])  # non vérifiée : source facultative

    def test_ceiling_needs_quantity_and_average_needs_end_date_and_no_quantity(self):
        no_qty = self.OK.replace('"0,9"', '')
        self.assertTrue(any('qty_value' in m for m in self.parse(no_qty)[1][0][1]))
        avg = 'moyenne_marche,Plantain,plantain,,kg,,500,,OCPV,https://ocpv-ci.com/,2026-06-01,,oui'
        self.assertTrue(any('valid_to' in m for m in self.parse(avg)[1][0][1]))
        self.assertEqual(self.parse(avg.replace(',,oui', ',2026-06-07,oui'))[1], [])
        with_qty = avg.replace('kg,,500', 'kg,1,500').replace(',,oui', ',2026-06-07,oui')
        self.assertTrue(any('qty_value' in m for m in self.parse(with_qty)[1][0][1]))

    def test_invalid_values_report_their_line(self):
        rows, errors, _ = self.parse(self.OK, self.OK.replace('2 200', '').replace('"1 200 FCFA"', '-5'),
                                     self.OK.replace('plafond', 'plafonnn'), self.OK.replace(',oui', ',peut-être'),
                                     self.OK.replace('01/01/2026', '2026-13-45'))
        self.assertEqual([n for n, _ in errors], [3, 4, 5, 6])
        self.assertEqual(len(rows), 1)

    def test_missing_columns_raise(self):
        with self.assertRaises(ValueError):
            ir.parse_csv(io.StringIO('kind,label\nplafond,x\n'))

    def test_end_before_start_is_rejected(self):
        bad = self.OK.replace(',,oui', ',2025-12-31,oui')
        self.assertTrue(any('antérieure' in m for m in self.parse(bad)[1][0][1]))


if __name__ == '__main__':
    unittest.main()
