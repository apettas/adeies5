"""Tests για κανονικοποίηση ονομάτων SSO."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from accounts.forms import CompleteSSORegistrationForm
from accounts.models import User, normalize_person_name_lower


class NormalizePersonNameTests(SimpleTestCase):
    def test_lowercase_greek_names(self):
        self.assertEqual(normalize_person_name_lower('  Γεώργιος  '), 'γεώργιος')
        self.assertEqual(normalize_person_name_lower('Νικολάου'), 'νικολάου')


class CompleteSSORegistrationFormTests(SimpleTestCase):
    def test_clean_name_fields_use_lowercase(self):
        form = CompleteSSORegistrationForm(target_email='test@sch.gr')
        form.cleaned_data = {'first_name': 'Μαρία'}
        self.assertEqual(form.clean_first_name(), 'μαρία')
        form.cleaned_data = {'last_name': 'Παπαδοπούλου'}
        self.assertEqual(form.clean_last_name(), 'παπαδοπούλου')
        form.cleaned_data = {'father_name': 'Ιωάννης'}
        self.assertEqual(form.clean_father_name(), 'ιωάννης')

    def test_name_accusative_required(self):
        form = CompleteSSORegistrationForm(target_email='test@sch.gr')
        form.cleaned_data = {'name_accusative': '   '}
        with self.assertRaises(ValidationError):
            form.clean_name_accusative()


class UserNameAccusativeSaveTests(TestCase):
    def test_manual_accusative_not_overwritten(self):
        user = User.objects.create(
            email='accusative@sch.gr',
            first_name='γεώργιος',
            last_name='νικολάου',
            name_accusative='γεώργιο νικολάου',
            is_active=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.name_accusative, 'γεώργιο νικολάου')

    def test_auto_accusative_when_blank(self):
        user = User.objects.create(
            email='autoacc@sch.gr',
            first_name='νίκος',
            last_name='παπαδόπουλος',
            is_active=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.name_accusative, 'νίκο παπαδόπουλο')
