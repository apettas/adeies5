"""Tests για SSO registration form και σχετική λογική."""
from django.test import SimpleTestCase, TestCase

from accounts.forms import CompleteSSORegistrationForm
from accounts.models import (
    User,
    Specialty,
    resolve_specialty_from_gsn_branch,
    apply_gsn_branch_specialty,
)


class CompleteSSORegistrationFormTests(TestCase):
    def test_psd_names_read_from_user_record(self):
        User.objects.create(
            email='names@sch.gr',
            first_name='Γεώργιος',
            last_name='Νικολάου',
            father_name='Ιωάννης',
            is_active=False,
        )
        form = CompleteSSORegistrationForm(target_email='names@sch.gr')
        form.cleaned_data = {
            'first_name': 'άλλο',
            'last_name': 'όνομα',
            'father_name': 'τεστ',
        }
        self.assertEqual(form.clean_first_name(), 'Γεώργιος')
        self.assertEqual(form.clean_last_name(), 'Νικολάου')
        self.assertEqual(form.clean_father_name(), 'Ιωάννης')


class EmployeeNumberReadonlyTests(TestCase):
    def test_employee_number_not_editable_by_user(self):
        User.objects.create(
            email='empno@sch.gr',
            first_name='Νίκος',
            last_name='Δοκιμής',
            employee_number='12345',
            is_active=False,
        )
        form = CompleteSSORegistrationForm(target_email='empno@sch.gr')
        form.cleaned_data = {'employee_number': '99999'}
        self.assertEqual(form.clean_employee_number(), '12345')

    def test_psd_branch_and_ou_not_editable(self):
        User.objects.create(
            email='psd@sch.gr',
            first_name='Νίκος',
            last_name='Δοκιμής',
            gsn_branch='ΠΕ02',
            sso_organizational_unit='1ο Λύκειο',
            is_active=False,
        )
        form = CompleteSSORegistrationForm(target_email='psd@sch.gr')
        form.cleaned_data = {
            'gsn_branch': 'ΠΕ99',
            'sso_organizational_unit': 'άλλη μονάδα',
        }
        self.assertEqual(form.clean_gsn_branch(), 'ΠΕ02')
        self.assertEqual(form.clean_sso_organizational_unit(), '1ο Λύκειο')

    def test_psd_title_not_editable(self):
        User.objects.create(
            email='title@sch.gr',
            first_name='Νίκος',
            last_name='Δοκιμής',
            role_description='Εκπαιδευτικός',
            is_active=False,
        )
        form = CompleteSSORegistrationForm(target_email='title@sch.gr')
        form.cleaned_data = {'role_description': 'Διοικητικός'}
        self.assertEqual(form.clean_role_description(), 'Εκπαιδευτικός')


class UserNameAccusativeSaveTests(TestCase):
    def test_manual_accusative_not_overwritten(self):
        user = User.objects.create(
            email='accusative@sch.gr',
            first_name='Γεώργιος',
            last_name='Νικολάου',
            name_accusative='Γεώργιο Νικολάου',
            is_active=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.name_accusative, 'Γεώργιο Νικολάου')

    def test_auto_accusative_when_blank(self):
        user = User.objects.create(
            email='autoacc@sch.gr',
            first_name='Νίκος',
            last_name='Παπαδόπουλος',
            is_active=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.name_accusative, 'Νίκο Παπαδόπουλο')


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
            first_name='Νίκος',
            last_name='Δοκιμής',
            gsn_branch='ΠΕ02',
            is_active=False,
        )
        apply_gsn_branch_specialty(user)
        self.assertEqual(user.specialty_id, self.specialty.pk)
