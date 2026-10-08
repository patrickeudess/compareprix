"""Tests : tolérance de l'import CSV aux formats d'Excel français (import_prices.py).
Lancer : python -m unittest test_import_prices -v"""
import io
import unittest
from datetime import date

import import_prices as ip

HEADER = 'article,supermarche,prix,unite,date_releve,source,statut,url,image_url\n'


def parse(*lines):
    return ip.parse_csv(io.StringIO(HEADER + '\n'.join(lines) + '\n'))


class TestNormalizeDate(unittest.TestCase):
    def test_french_formats_become_iso(self):
        for raw in ('08/10/2026', '8/10/2026', '08-10-2026', '08.10.2026', '08/10/2026 00:00:00'):
            self.assertEqual(ip.normalize_date(raw), '2026-10-08', raw)

    def test_day_first_is_never_swapped_with_month(self):
        self.assertEqual(ip.normalize_date('03/04/2026'), '2026-04-03')  # 3 avril, pas 4 mars

    def test_iso_and_garbage_are_left_untouched(self):
        for raw in ('2026-10-08', '31/02/2026', '08/10/26', 'hier', ''):
            self.assertEqual(ip.normalize_date(raw), raw, raw)


class TestNormalizePrice(unittest.TestCase):
    def test_thousand_separators_currency_and_trailing_zeros(self):
        for raw in ('2500', '2 500', '2 500', '2 500', '2500 FCFA', '2 500 F CFA', '2500F', '2 500,00', '2500.0'):
            self.assertEqual(ip.normalize_price(raw), '2500', repr(raw))

    def test_non_integer_prices_are_not_rounded(self):
        for raw in ('2500,5', '2500.75', 'gratuit', '12 34', '-5'):
            self.assertEqual(ip.normalize_price(raw), raw, raw)


class TestParseCsv(unittest.TestCase):
    def test_excel_style_row_is_accepted_end_to_end(self):
        today = date.today()
        rows, errors, skipped = parse(f'Riz parfumé 5kg,Carrefour,"2 500 FCFA",kg,{today.strftime("%d/%m/%Y")},manuel,a_verifier,,')
        self.assertEqual(errors, [])
        self.assertEqual((rows[0]['prix'], rows[0]['date_releve']), (2500, today.isoformat()))

    def test_blank_price_rows_are_still_skipped(self):
        rows, errors, skipped = parse('Riz parfumé 5kg,Carrefour,,kg,,manuel,a_verifier,,')
        self.assertEqual((rows, errors, skipped), ([], [], 1))

    def test_bad_values_are_still_rejected_with_their_line_number(self):
        rows, errors, skipped = parse(f'Riz,Carrefour,2500,kg,{date.today().isoformat()},manuel,a_verifier,,',
                                      f'Huile,Carrefour,2500 euros,L,{date.today().isoformat()},manuel,a_verifier,,',
                                      'Sucre,Carrefour,900,kg,31/02/2026,manuel,a_verifier,,')
        self.assertEqual([n for n, _ in errors], [3, 4])


if __name__ == '__main__':
    unittest.main()
