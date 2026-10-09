#!/usr/bin/env python3
"""Remplace l'adresse de l'application dans les pages de redirection GitHub Pages (index.html, panier.html...).

    python tools/set_site_url.py https://www.exemple.ci            # simulation : liste ce qui changerait
    python tools/set_site_url.py https://www.exemple.ci --apply    # écrit les fichiers

À lancer une fois que le nouveau domaine fonctionne (voir tools/check_domain.py), puis à committer.
L'ancienne adresse est détectée dans index.html ; --old=https://... permet de la donner explicitement.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ('index.html', 'panier.html', 'compte.html', 'contribuer.html', 'commercant.html', '404.html')
ORIGIN = re.compile(r'https://[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+')


def read(path):
    with open(path, encoding='utf-8', newline='') as f:  # newline='' : fins de ligne conservées
        return f.read()


def detect_old(root):
    match = re.search(r"new URL\(\"[^\"]*\",'(https://[^']+)'\)", read(os.path.join(root, 'index.html')))
    return match.group(1) if match else None


def plan(root, new, old=None):
    """Retourne (ancienne adresse, {fichier: nombre de remplacements}) sans rien écrire."""
    old = old or detect_old(root)
    if not old:
        raise ValueError("Ancienne adresse introuvable dans index.html : indiquez --old=https://...")
    counts = {}
    for name in PAGES:
        path = os.path.join(root, name)
        if os.path.exists(path):
            n = read(path).count(old)
            if n:
                counts[name] = n
    return old, counts


def apply(root, new, old):
    for name in PAGES:
        path = os.path.join(root, name)
        if os.path.exists(path):
            text = read(path)
            if old in text:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(text.replace(old, new))


def valid_origin(value):
    return bool(ORIGIN.fullmatch(value))


def main(argv, root=ROOT):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 1:
        sys.exit(__doc__)
    new = args[0].rstrip('/')
    if not valid_origin(new):
        sys.exit(f"Adresse invalide : « {args[0]} ». Attendu : https://nom.de.domaine (sans chemin, en HTTPS).")
    explicit = next((a.split('=', 1)[1].rstrip('/') for a in argv if a.startswith('--old=')), None)
    try:
        old, counts = plan(root, new, explicit)
    except ValueError as error:
        sys.exit(str(error))
    if old == new:
        print('Rien à faire : les pages pointent déjà vers', new)
        return 0
    total = sum(counts.values())
    for name, n in counts.items():
        print(f'  {name}: {n} occurrence(s)')
    print(f'{old} -> {new} : {total} remplacement(s) dans {len(counts)} fichier(s)')
    if '--apply' in argv:
        apply(root, new, old)
        print('Fichiers écrits. Vérifiez avec « git diff », puis committez.')
    else:
        print('Simulation uniquement. Relancez avec --apply pour écrire.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
