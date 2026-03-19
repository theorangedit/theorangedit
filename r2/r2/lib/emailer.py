# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################

from email import encoders
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.errors import HeaderParseError
import datetime
import traceback, sys
from smtplib import SMTP_SSL,SMTP

from r2.lib.context import c
from r2.lib.app_globals import g
import simplejson as json

from r2.config import feature
from r2.lib import hooks
from r2.lib.ratelimit import SimpleRateLimit
from r2.lib.utils import timeago
from r2.models import Comment, Email, DefaultSR, Account, Award
from r2.models.token import EmailVerificationToken, PasswordResetToken


trylater_hooks = hooks.HookRegistrar()

async def _system_email(db, email, plaintext_body, kind, reply_to="",
        thing=None, from_address=g.feedback_email,
        html_body="", list_unsubscribe_header="", user=None,
        suppress_username=False):
    """
    For sending email from the system to a user (reply address will be
    feedback and the name will be reddit.com)
    """
    if suppress_username:
        user = None
    elif user is None and c.user_is_loggedin:
        user = c.user

    await Email.handler.add_to_queue(db, user,
        email, g.domain, from_address, kind,
        body=plaintext_body, reply_to=reply_to, thing=thing,
    )


async def _ads_email(db, body, from_name, kind):
    """
    For sending email to ads
    """
    await Email.handler.add_to_queue(db, None, g.ads_email, from_name,
                                     g.ads_email, kind, body=body)

async def _fraud_email(db, body, kind):
    """
    For sending email to the fraud mailbox
    """
    await Email.handler.add_to_queue(db, None, g.fraud_email, g.domain,
                                     g.fraud_email, kind, body=body)

async def _community_email(db, body, kind):
    """
    For sending email to the community mailbox
    """
    await Email.handler.add_to_queue(db, c.user, g.community_email, g.domain,
                                     g.community_email, kind, body=body)

async def verify_email(db, user, dest=None):
    """
    For verifying an email address
    """
    from r2.lib.pages import VerifyEmail
    user.email_verified = False
    user._commit()
    Award.take_away("verified_email", user)

    token = EmailVerificationToken._new(user)
    base = g.https_endpoint or g.origin
    emaillink = base + '/verification/' + token._id
    if dest:
        emaillink += f'?dest={dest}'
    g.log.debug("Generated email verification link: " + emaillink)

    await _system_email(db, user.email,
                        VerifyEmail(user=user,
                                    emaillink=emaillink).render(style='email'),
                        Email.Kind.VERIFY_EMAIL)

async def password_email(db, user):
    """
    For resetting a user's password.
    """
    from r2.lib.pages import PasswordReset

    user_reset_ratelimit = SimpleRateLimit(
        name=f"email_reset_count_{user._id36}",
        seconds=int(datetime.timedelta(hours=12).total_seconds()),
        limit=3,
    )
    if not user_reset_ratelimit.record_and_check():
        return False

    global_reset_ratelimit = SimpleRateLimit(
        name="email_reset_count_global",
        seconds=int(datetime.timedelta(hours=1).total_seconds()),
        limit=1000,
    )
    if not global_reset_ratelimit.record_and_check():
        raise ValueError("password reset ratelimit exceeded")

    token = PasswordResetToken._new(user)
    base = g.https_endpoint or g.origin
    passlink = base + '/resetpassword/' + token._id
    g.log.info("Generated password reset link: " + passlink)
    await _system_email(db, user.email,
                        PasswordReset(user=user,
                                      passlink=passlink).render(style='email'),
                        Email.Kind.RESET_PASSWORD,
                        user=user,
                        )
    return True

@trylater_hooks.on('trylater.message_notification_email')
async def message_notification_email(db, data):
    """Queues a system email for a new message notification."""
    from r2.lib.pages import MessageNotificationEmail

    MAX_EMAILS_PER_DAY = 1000
    MESSAGE_THROTTLE_KEY = 'message_notification_emails'

    # If our counter's expired, initialize it again.
    g.cache.add(MESSAGE_THROTTLE_KEY, 0, time=24*60*60)

    for datum in data.values():
        datum = json.loads(datum)
        user = Account._byID36(datum['to'], data=True)
        comment = Comment._by_fullname(datum['comment'], data=True)

        # In case a user has enabled the preference while it was enabled for
        # them, but we've since turned it off.  We need to explicitly state the
        # user because we're not in the context of an HTTP request from them.
        if not feature.is_enabled('orangereds_as_emails', user=user):
            continue

        if g.cache.get(MESSAGE_THROTTLE_KEY) > MAX_EMAILS_PER_DAY:
            raise Exception(
                    'Message notification emails: safety limit exceeded!')

        mac = generate_notification_email_unsubscribe_token(
                datum['to'], user_email=user.email,
                user_password_hash=user.password)
        base = g.https_endpoint or g.origin
        unsubscribe_link = base + f"/mail/unsubscribe/{datum['to']}/{mac}"

        templateData = {
            'sender_username': datum.get('from', ''),
            'comment': comment,
            'permalink': datum['permalink'],
            'unsubscribe_link': unsubscribe_link,
        }
        await _system_email(db, user.email,
                            MessageNotificationEmail(**templateData).render(style='email'),
                            Email.Kind.MESSAGE_NOTIFICATION,
                            from_address=g.notification_email)

        g.stats.simple_event('email.message_notification.queued')
        g.cache.incr(MESSAGE_THROTTLE_KEY)

def generate_notification_email_unsubscribe_token(user_id36, user_email=None,
                                                  user_password_hash=None):
    """Generate a token used for one-click unsubscribe links for notification
    emails.

    user_id36: A base36-encoded user id.
    user_email: The user's email.  Looked up if not provided.
    user_password_hash: The hash of the user's password.  Looked up if not
                        provided.
    """
    import hashlib
    import hmac

    if (not user_email) or (not user_password_hash):
        user = Account._byID36(user_id36, data=True)
        if not user_email:
            user_email = user.email
        if not user_password_hash:
            user_password_hash = user.password

    return hmac.new(
        g.secrets['email_notifications'],
        user_id36 + user_email + user_password_hash,
        hashlib.sha256).hexdigest()

async def password_change_email(db, user):
    """Queues a system email for a password change notification."""
    from r2.lib.pages import PasswordChangeEmail

    return await _system_email(db, user.email,
                               PasswordChangeEmail(user=user).render(style='email'),
                               Email.Kind.PASSWORD_CHANGE,
                               user=user,
                               )

async def email_change_email(db, user):
    """Queues a system email for a email change notification."""
    from r2.lib.pages import EmailChangeEmail

    return await _system_email(db, user.email,
                               EmailChangeEmail(user=user).render(style='email'),
                               Email.Kind.EMAIL_CHANGE)

async def community_email(db, body, kind):
    return await _community_email(db, body, kind)


async def ads_email(db, body, from_name=g.domain):
    """Queues an email to the Sales team."""
    return await _ads_email(db, body, from_name, Email.Kind.ADS_ALERT)

async def share(db, link, emails, from_name="", reply_to="", body=""):
    """Queues a 'share link' email."""
    now = datetime.datetime.now(g.tz)
    ival = now - timeago(g.new_link_share_delay)
    date = max(now, link._date + ival)
    await Email.handler.add_to_queue(db, c.user, emails, from_name, g.share_reply,
                                     Email.Kind.SHARE, date=date,
                                     body=body, reply_to=reply_to,
                                     thing=link)

async def send_queued_mail(db, test=False):
    """sends mail from the mail queue to smtplib for delivery.  Also,
    on successes, empties the mail queue and adds all emails to the
    sent_mail list."""
    from r2.lib.pages import Share, Mail_Opt
    now = datetime.datetime.now(g.tz)
    if not c.site:
        c.site = DefaultSR()

    clear = False
    if not test:
        session = SMTP(g.smtp_server, 587)
    async def sendmail(email):
        try:
            mimetext = email.to_MIMEText()
            if mimetext is None:
                print(f"Got None mimetext for email from {email.fr_addr!r} and to {email.to_addr!r}")
            if test:
                print(mimetext.as_string())
                print(g.smtp_server)
            else:
                session.starttls()
                session.login(email.fr_addr, g.smtp_password)
                session.sendmail(email.fr_addr, email.to_addr,
                                 mimetext.as_string())
                await email.set_sent(db, rejected=False)
                session.quit()
        # exception happens only for local recipient that doesn't exist
        except:
                #(SMTP_SSL.SMTPRecipientsRefused, SMTP_SSL.SMTPSenderRefused,
                #UnicodeDecodeError, AttributeError, HeaderParseError):
            # handle error and print, but don't stall the rest of the queue
            print("Handled error sending mail (traceback to follow)")
            traceback.print_exc(file=sys.stdout)
            await email.set_sent(db, rejected=True)


    try:
        async for email in Email.get_unsent(db, now):
            clear = True

            should_queue = email.should_queue()
            # check only on sharing that the mail is invalid
            if email.kind == Email.Kind.SHARE:
                if should_queue:
                    email.body = Share(username=email.from_name(),
                                       msg_hash=email.msg_hash,
                                       link=email.thing,
                                       body=email.body).render(style="email")
                else:
                    await email.set_sent(db, rejected=True)
                    continue
            elif email.kind == Email.Kind.OPTOUT:
                email.body = Mail_Opt(msg_hash=email.msg_hash,
                                      leave=True).render(style="email")
            elif email.kind == Email.Kind.OPTIN:
                email.body = Mail_Opt(msg_hash=email.msg_hash,
                                      leave=False).render(style="email")
            # handle unknown types here
            elif not email.body:
                print(f"Rejecting email with an empty body from {email.fr_addr!r} and to {email.to_addr!r}")
                await email.set_sent(db, rejected=True)
                continue
            await sendmail(email)

    except Exception:
        print("Error sending queued mail")

    # clear is true if anything was found and processed above
    if clear:
        await Email.handler.clear_queue(db, now)



async def opt_out(db, msg_hash):
    """Queues an opt-out email (i.e., a confirmation that the email
    address has been opted out of receiving any future mail)"""
    email, added = await Email.handler.opt_out(db, msg_hash)
    if email and added:
        await _system_email(db, email, "", Email.Kind.OPTOUT)
    return email, added

async def opt_in(db, msg_hash):
    """Queues an opt-in email (i.e., that the email has been removed
    from our opt out list)"""
    email, removed = await Email.handler.opt_in(db, msg_hash)
    if email and removed:
        await _system_email(db, email, "", Email.Kind.OPTIN)
    return email, removed


async def _promo_email(db, thing, kind, body="", **kw):
    from r2.lib.pages import Promo_Email
    a = Account._byID(thing.author_id, True)

    if not a.email:
        return

    body = Promo_Email(link=thing, kind=kind,
                       body=body, **kw).render(style="email")
    return await _system_email(db, a.email, body, kind, thing=thing,
                               reply_to=g.selfserve_support_email,
                               suppress_username=True)


async def new_promo(db, thing):
    return await _promo_email(db, thing, Email.Kind.NEW_PROMO)

async def promo_total_budget(db, thing, total_budget_dollars, start_date):
    return await _promo_email(db, thing, Email.Kind.BID_PROMO,
        total_budget_dollars=total_budget_dollars, start_date=start_date)

async def accept_promo(db, thing):
    return await _promo_email(db, thing, Email.Kind.ACCEPT_PROMO)

async def reject_promo(db, thing, reason=""):
    return await _promo_email(db, thing, Email.Kind.REJECT_PROMO, reason)

async def edited_live_promo(db, thing):
    return await _promo_email(db, thing, Email.Kind.EDITED_LIVE_PROMO)

async def queue_promo(db, thing, total_budget_dollars, trans_id):
    return await _promo_email(db, thing, Email.Kind.QUEUED_PROMO,
        total_budget_dollars=total_budget_dollars, trans_id=trans_id)

async def live_promo(db, thing):
    return await _promo_email(db, thing, Email.Kind.LIVE_PROMO)

async def finished_promo(db, thing):
    return await _promo_email(db, thing, Email.Kind.FINISHED_PROMO)


async def refunded_promo(db, thing):
    return await _promo_email(db, thing, Email.Kind.REFUNDED_PROMO)


async def void_payment(db, thing, campaign, total_budget_dollars, reason):
    return await _promo_email(db, thing, Email.Kind.VOID_PAYMENT, campaign=campaign,
                              total_budget_dollars=total_budget_dollars,
                              reason=reason)


async def fraud_alert(db, body):
    return await _fraud_email(db, body, Email.Kind.FRAUD_ALERT)

async def suspicious_payment(db, user, link):
    from r2.lib.pages import SuspiciousPaymentEmail

    body = SuspiciousPaymentEmail(user, link).render(style="email")
    kind = Email.Kind.SUSPICIOUS_PAYMENT

    return await _fraud_email(db, body, kind)


def send_html_email(to_addr, from_addr, subject, html,
        subtype="html", attachments=None):
    from r2.lib.filters import _force_utf8
    if not attachments:
        attachments = []

    msg = MIMEMultipart()
    msg.attach(MIMEText(_force_utf8(html), subtype))
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    for attachment in attachments:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(attachment['contents'])
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment',
            filename=attachment['name'])
        msg.attach(part)

    session = SMTP(g.smtp_server, 465)
    session.login(from_addr, g.smtp_password)
    session.sendmail(from_addr, to_addr, msg.as_string())
    session.quit()

trylater_hooks.register_all()
