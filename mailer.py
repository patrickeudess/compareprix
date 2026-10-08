"""Envoi d'emails transactionnels (codes de vérification) par SMTP, sans dépendance.

Configuration par variables d'environnement (jamais dans le dépôt) :
  COMPAREPRIX_SMTP_HOST      ex. smtp-relay.brevo.com   (absent = envoi désactivé)
  COMPAREPRIX_SMTP_PORT      587 (STARTTLS, défaut) ou 465 (SSL direct)
  COMPAREPRIX_SMTP_SECURITY  starttls | ssl | none (défaut : selon le port). `none` : relais local de confiance uniquement.
  COMPAREPRIX_SMTP_USER / COMPAREPRIX_SMTP_PASSWORD
  COMPAREPRIX_SMTP_FROM      ex. "ComparePrix <no-reply@votre-domaine.ci>"

Un SMS suivrait le même modèle : une fonction `send_*` qui appelle l'API d'un fournisseur.
Il n'est pas fourni, car il exige un compte payant chez un fournisseur (identifiants que le dépôt ne contient pas).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


class MailNotConfigured(RuntimeError):
    """Aucun serveur SMTP configuré."""


SECURITY_MODES = ('starttls', 'ssl', 'none')


def _security():
    """Mode de chiffrement demandé, ou None si la valeur est inconnue (faute de frappe, espace...)."""
    try:
        default = 'ssl' if int(os.environ.get('COMPAREPRIX_SMTP_PORT', '587')) == 465 else 'starttls'
    except ValueError:
        return None
    mode = os.environ.get('COMPAREPRIX_SMTP_SECURITY', default).strip().lower()
    return mode if mode in SECURITY_MODES else None


def is_configured():
    """Un mode de chiffrement invalide désactive l'envoi plutôt que de retomber en clair."""
    return bool(os.environ.get('COMPAREPRIX_SMTP_HOST') and os.environ.get('COMPAREPRIX_SMTP_FROM') and _security())


def send_mail(to, subject, body):
    """Envoie un email texte. Lève MailNotConfigured sans configuration, OSError/SMTPException en cas d'échec réseau."""
    if not is_configured():
        raise MailNotConfigured('SMTP non configuré')
    host = os.environ['COMPAREPRIX_SMTP_HOST']
    port = int(os.environ.get('COMPAREPRIX_SMTP_PORT', '587'))
    user = os.environ.get('COMPAREPRIX_SMTP_USER')
    password = os.environ.get('COMPAREPRIX_SMTP_PASSWORD', '')
    message = EmailMessage()
    message['From'] = os.environ['COMPAREPRIX_SMTP_FROM']
    message['To'] = to
    message['Subject'] = subject
    message.set_content(body)
    security = _security()
    context = ssl.create_default_context()
    if security == 'ssl':
        server = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    with server:
        if security == 'starttls':
            server.starttls(context=context)
        if user:
            server.login(user, password)
        server.send_message(message)
