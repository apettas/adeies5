"""Custom CAS backend για ΠΣΔ (sch.gr) — SSO integration."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpRequest
from django_cas_ng.backends import CASBackend
from django_cas_ng.signals import cas_user_authenticated
from django_cas_ng.utils import get_cas_client

logger = logging.getLogger(__name__)


class PdedeCASBackend(CASBackend):
    """
    CAS backend προσαρμοσμένο για ΠΔΕΔΕ:
    - Επιτρέπει σύνδεση PENDING/inactive χρηστών (το workflow τα χειρίζεται μετά)
    - Κανονικοποιεί mail → email
    - Ρυθμίζει νέους χρήστες σε PENDING
    """

    def user_can_authenticate(self, user):
        return user is not None

    def configure_user(self, user):
        user.registration_status = 'PENDING'
        user.is_active = False
        if not user.first_name:
            user.first_name = '—'
        if not user.last_name:
            user.last_name = '—'
        user.save()
        return user

    def authenticate(self, request: HttpRequest, ticket: str, service: str):
        client = get_cas_client(service_url=service, request=request)
        username, attributes, pgtiou = client.verify_ticket(ticket)

        if attributes and request:
            request.session['attributes'] = attributes

        if attributes:
            if not attributes.get('email') and attributes.get('mail'):
                attributes['email'] = attributes['mail']

            for cas_attr_name, model_field in settings.CAS_RENAME_ATTRIBUTES.items():
                if cas_attr_name in attributes and cas_attr_name != model_field:
                    attributes[model_field] = attributes[cas_attr_name]
                    attributes.pop(cas_attr_name, None)

        if settings.CAS_USERNAME_ATTRIBUTE != 'cas:user' and settings.CAS_VERSION != 'CAS_2_SAML_1_0':
            if attributes:
                username = (
                    attributes.get(settings.CAS_USERNAME_ATTRIBUTE)
                    or attributes.get('email')
                    or attributes.get('mail')
                )
            else:
                logger.warning('CAS: ticket OK but no attributes returned')
                return None

        if not username:
            logger.warning('CAS: no username/email in attributes: %s', attributes)
            return None

        username = self.clean_username(username)

        if attributes:
            reject = self.bad_attributes_reject(request, username, attributes)
            if reject:
                return None

        UserModel = get_user_model()

        if settings.CAS_CREATE_USER:
            user_kwargs = {UserModel.USERNAME_FIELD: username}
            if settings.CAS_CREATE_USER_WITH_ID:
                user_kwargs['id'] = self.get_user_id(attributes)

            user, created = UserModel._default_manager.get_or_create(**user_kwargs)
            if created:
                user = self.configure_user(user)
        else:
            created = False
            user = None
            try:
                if settings.CAS_LOCAL_NAME_FIELD:
                    user = UserModel._default_manager.get(
                        **{settings.CAS_LOCAL_NAME_FIELD: username}
                    )
                else:
                    user = UserModel._default_manager.get_by_natural_key(username)
            except UserModel.DoesNotExist:
                logger.warning('CAS: user %s not found and CAS_CREATE_USER=False', username)
                return None

        if not self.user_can_authenticate(user):
            return None

        if pgtiou and settings.CAS_PROXY_CALLBACK and request:
            request.session['pgtiou'] = pgtiou

        if settings.CAS_MAP_AFFILIATIONS and user and attributes:
            affils = attributes.get(settings.CAS_AFFILIATIONS_KEY, [])
            for affil in affils:
                if affil:
                    group, _ = Group.objects.get_or_create(name=affil)
                    user.groups.add(group)

        if settings.CAS_AFFILIATIONS_HANDLERS and user and attributes:
            affils = attributes.get(settings.CAS_AFFILIATIONS_KEY, [])
            for handler in settings.CAS_AFFILIATIONS_HANDLERS:
                if callable(handler):
                    handler(user, affils)

        if settings.CAS_APPLY_ATTRIBUTES_TO_USER and attributes and user:
            user_model_fields = {f.name for f in UserModel._meta.fields}
            for field in UserModel._meta.fields:
                if not field.null and field.name in attributes and attributes[field.name] is None:
                    attributes[field.name] = ''
                if field.get_internal_type() == 'BooleanField' and field.name in attributes:
                    attributes[field.name] = attributes[field.name] == 'True'

            for key, value in attributes.items():
                if key != 'username' and key in user_model_fields:
                    setattr(user, key, value)

            if settings.CAS_CREATE_USER or user:
                user.save()

        cas_user_authenticated.send(
            sender=self,
            user=user,
            created=created,
            username=username,
            attributes=attributes,
            pgtiou=pgtiou,
            ticket=ticket,
            service=service,
            request=request,
        )
        return user
