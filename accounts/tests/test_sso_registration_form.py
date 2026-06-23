"""Tests για κανονικοποίηση ονομάτων SSO."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from accounts.forms import CompleteSSORegistrationForm
from accounts.models import (
    User,
    Specialty,
    normalize_person_name_lower,
    validate_greek_name_characters,
    resolve_specialty_from_gsn_branch,
    apply_gsn_branch_specialty,
)


class NormalizePersonNameTests(SimpleTestCase):
    def test_lowercase_greek_names(self):
        self.assertEqual(normalize_person_name_lower('  Γεώργιος  '), 'γεώργιος')
        self.assertEqual(normalize_person_name_lower('Νικολάου'), 'νικολάου')


class GreekNameCharacterValidationTests(SimpleTestCase):
    def test_rejects_latin_letter_in_greek_name(self):
        with self.assertRaises(ValidationError):
            validate_greek_name_characters('\u0041νδρεας', 'Όνομα')

    def test_accepts_pure_greek_name(self):
        validate_greek_name_characters('Ανδρέας', 'Όνομα')


class CompleteSSORegistrationFormTests(SimpleTestCase):
    def test_clean_name_fields_use_lowercase(self):
        form = CompleteSSORegistrationForm(target_email='test@sch.gr')
        form.cleaned_data = {'first_name': 'Ανδρέας'}
        self.assertEqual(form.clean_first_name(), 'ανδρέας')
        form.cleaned_data = {'last_name': 'Παπαδοπούλου'}
        self.assertEqual(form.clean_last_name(), 'παπαδοπούλου')
        form.cleaned_data = {'father_name': 'Ιωάννης'}
        self.assertEqual(form.clean_father_name(), 'ιωάννης')

    def test_clean_name_fields_reject_latin_characters(self):
        form = CompleteSSORegistrationForm(target_email='test@sch.gr')
        form.cleaned_data = {'first_name': '\u0041νδρεας'}
        with self.assertRaises(ValidationError):
            form.clean_first_name()

    def test_name_accusative_required(self):
        form = CompleteSSORegistrationForm(target_email='test@sch.gr')
        form.cleaned_data = {'name_accusative': '   '}
        with self.assertRaises(ValidationError):
            form.clean_name_accusative()

    def test_name_accusative_normalized_to_lowercase(self):
        form = CompleteSSORegistrationForm(target_email='test@sch.gr')
        form.cleaned_data = {'name_accusative': '  Γεώργιο Νικολάου  '}
        self.assertEqual(form.clean_name_accusative(), 'γεώργιο νικολάου')


class EmployeeNumberReadonlyTests(TestCase):
    def test_employee_number_not_editable_by_user(self):
        User.objects.create(
            email='empno@sch.gr',
            first_name='νίκος',
            last_name='δοκιμής',
            employee_number='12345',
            is_active=False,
        )
        form = CompleteSSORegistrationForm(target_email='empno@sch.gr')
        form.cleaned_data = {'employee_number': '99999'}
        self.assertEqual(form.clean_employee_number(), '12345')


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


class SpecialtyFromGsnBranchTests(TestCase):
    def setUp(self):
        self.specialty = Specialty.objects.create(
            specialties_short='ΠΕ02',
            specialties_full='ΦΙΛΟΛΟΓΟΙ',
            is_active=True,
        )

    def test_resolve_specialty_from_short_code(self):
        self.assertEqual(
            resolve_specialty_from_gsn_branch('ΠΕ02'),
            self.specialty,
        )

    def test_resolve_specialty_case_insensitive(self):
        self.assertEqual(
            resolve_specialty_from_gsn_branch('πε02'),
            self.specialty,
        )

    def test_apply_gsn_branch_specialty_on_user(self):
        user = User.objects.create(
            email='branch@sch.gr',
            first_name='νίκος',
            last_name='δοκιμής',
            gsn_branch='ΠΕ02',
            is_active=False,
        )
        apply_gsn_branch_specialty(user)
        self.assertEqual(user.specialty_id, self.specialty.pk)
