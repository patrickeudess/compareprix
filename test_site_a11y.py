"""Garde-fous d'accessibilité du site statique (CSS et HTML), sans navigateur ni dépendance.

Ils empêchent de défaire les corrections issues de l'audit UI/UX : contrastes, taille minimale du texte,
cibles tactiles, icônes SVG de navigation, barre du panier masquée quand elle est vide.
Lancer : python -m unittest test_site_a11y -v
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES = ('index.html', 'panier.html', 'compte.html', 'contribuer.html')


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as f:
        return f.read()


def luminance(hex_color):
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


class TestContrast(unittest.TestCase):
    CSS = read('static', 'product-design.css')
    # fonds sur lesquels le texte secondaire est posé : page, cartes, pastille du compteur de panier
    BACKGROUNDS = ('#f4f7f3', '#f5f7f3', '#ffffff', '#dcece0', '#e3f0e7')

    def test_secondary_text_color_reaches_aa_on_every_background(self):
        for bg in self.BACKGROUNDS:
            self.assertGreaterEqual(contrast('#5c6c62', bg), 4.5, f'#5c6c62 sur {bg}')

    def test_old_low_contrast_colors_are_gone(self):
        for old in ('#64776d', '#6e7e73'):
            self.assertNotIn(old, self.CSS, f'{old} (contraste < 4,5:1) a été réintroduit')
            for page in PAGES:
                self.assertNotIn(old, read(page), f'{old} réintroduit dans {page}')

    def test_measured_old_values_really_failed(self):
        # garde-fou du test lui-même : les anciennes valeurs étaient bien sous le seuil sur le fond de page
        self.assertLess(contrast('#6e7e73', '#f4f7f3'), 4.5)
        self.assertLess(contrast('#64776d', '#dcece0'), 4.5)


class TestTextSize(unittest.TestCase):
    def test_no_font_size_below_12px_in_any_stylesheet(self):
        sources = {'product-design.css': read('static', 'product-design.css')}
        for page in PAGES:
            sources[page] = ' '.join(re.findall(r'<style[^>]*>(.*?)</style>', read(page), re.S))
        for name, css in sources.items():
            for value in re.findall(r'font-size:\s*(\d*\.?\d+)rem', css):
                self.assertGreaterEqual(float(value) * 16, 12, f'{name}: font-size {value}rem < 12 px')
            for value in re.findall(r'font-size:\s*(\d*\.?\d+)px', css):
                self.assertGreaterEqual(float(value), 12, f'{name}: font-size {value}px < 12 px')


class TestTouchTargets(unittest.TestCase):
    CSS = read('static', 'product-design.css')

    def test_touch_target_block_present_with_44px_minimum(self):
        self.assertIn('Touch Target Size', self.CSS)
        rule = re.search(r'([^{}]*\.offer-actions button[^{}]*)\{[^}]*min-height:\s*44px', self.CSS)
        self.assertIsNotNone(rule, 'la règle min-height:44px des actions d\'offre a disparu')
        for selector in ('.offer-actions a', '.product-link', '.suggestions button', '.basket-line button',
                         '.basket-line input', '.quick-help summary', '.page-nav a'):
            self.assertIn(selector, rule.group(1), f'{selector} n\'a plus de hauteur minimale de 44 px')
        self.assertRegex(self.CSS, r'select\{min-height:\s*44px\}')

    def test_gap_between_adjacent_targets_is_at_least_8px(self):
        gaps = [int(g) for g in re.findall(r'\.offer-actions\{[^}]*?gap:\s*(\d+)px', self.CSS)]
        self.assertTrue(gaps and gaps[-1] >= 8, gaps)


class TestNavigationIcons(unittest.TestCase):
    EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')

    def test_navigation_uses_svg_icons_not_emoji(self):
        for page in PAGES:
            nav = re.search(r'<nav[^>]*class="page-nav".*?</nav>', read(page), re.S).group(0)
            self.assertEqual(self.EMOJI.findall(nav), [], f'{page}: emoji dans la navigation')
            self.assertEqual(nav.count('<svg'), 4, f'{page}: 4 icônes SVG attendues')
            self.assertEqual(nav.count('aria-hidden="true"'), 4, f'{page}: icônes décoratives à masquer aux lecteurs d\'écran')
            self.assertNotIn('<img', nav)

    def test_svg_icons_inherit_text_color(self):
        for page in PAGES:
            for svg in re.findall(r'<svg[^>]*>', read(page)):
                self.assertIn('stroke="currentColor"', svg)  # suit le contraste du texte et l'état actif
                self.assertIn('focusable="false"', svg)


class TestBasketDock(unittest.TestCase):
    def test_dock_starts_hidden_and_css_honours_hidden(self):
        self.assertRegex(read('index.html'), r'<a class="basket-dock" hidden ')
        self.assertIn('.basket-dock[hidden]{display:none}', read('static', 'product-design.css'))

    def test_script_shows_dock_only_when_basket_not_empty(self):
        self.assertIn("dock.hidden=count===0", read('static', 'basket.js'))


class TestFluidity(unittest.TestCase):
    CSS = read('static', 'product-design.css')
    JS = read('static', 'compareprix.js')

    def test_new_controls_keep_44px_touch_targets(self):
        for selector in ('.sort-seg button', '.offer-more>summary', '.offer-actions .share-link', '.offer-more>button'):
            rule = re.search(re.escape(selector) + r'\{[^}]*min-height:\s*44px', self.CSS)
            self.assertIsNotNone(rule, f'{selector} : hauteur minimale de 44 px absente')
        self.assertRegex(self.CSS, r'\.filters-box>summary\{[^}]*min-height:\s*48px')

    def test_entry_animation_and_skeleton_stop_when_reduced_motion_is_requested(self):
        block = re.search(r'@media\(prefers-reduced-motion:reduce\)\{(.*)\}\s*(?:@|$)', self.CSS, re.S)
        reduced = ''.join(re.findall(r'@media\(prefers-reduced-motion:reduce\)\{(.*?)\}\}', self.CSS, re.S)) or (block.group(1) if block else '')
        self.assertIn('.offer:not(.skeleton){animation:none}', reduced)
        self.assertIn('.offer.skeleton{animation:none}', reduced)

    def test_whatsapp_share_link_is_safe(self):
        self.assertIn("share.href='https://wa.me/?text='+encodeURIComponent(", self.JS)
        self.assertIn("share.rel='noopener noreferrer'", self.JS)

    def test_skeleton_cards_are_hidden_from_screen_readers(self):
        self.assertIn("placeholder.setAttribute('aria-hidden','true')", self.JS)

    def test_secondary_details_are_folded_and_filters_collapsed(self):
        self.assertIn("more.className='offer-more'", self.JS)
        self.assertIn("filtersBox.className='filters-box'", self.JS)
        self.assertNotIn("['Comparer par',orderFilter]", self.JS)  # le tri est un sélecteur à deux boutons


if __name__ == '__main__':
    unittest.main()
