"""Tests για CAS attribute mapping από Σχολικό Δίκτυο."""
from django.test import SimpleTestCase, override_settings

from accounts.cas_backend import _apply_cas_attribute_aliases


@override_settings(
    CAS_RENAME_ATTRIBUTES={
        'givenName': 'first_name',
        'sn': 'last_name',
        'gsnfathername': 'father_name',
        'employeeNumber': 'employee_number',
        'gsnBranch': 'gsn_branch',
        'title': 'role_description',
        'Title': 'role_description',
        'ou': 'sso_organizational_unit',
        'mail': 'email',
    },
)
class CASAttributeMappingTests(SimpleTestCase):
    def test_maps_psd_attributes_to_user_fields(self):
        attributes = {
            'mail': 'teacher@sch.gr',
            'gsnfathername': 'Γεώργιος',
            'employeeNumber': '12345',
            'gsnBranch': 'ΠΕ02',
            'Title': 'Εκπαιδευτικός',
            'ou': '1ο Λύκειο Νέου Ψυχικού',
        }
        mapped = _apply_cas_attribute_aliases(attributes.copy())
        self.assertEqual(mapped['email'], 'teacher@sch.gr')
        self.assertEqual(mapped['father_name'], 'Γεώργιος')
        self.assertEqual(mapped['employee_number'], '12345')
        self.assertEqual(mapped['gsn_branch'], 'ΠΕ02')
        self.assertEqual(mapped['role_description'], 'Εκπαιδευτικός')
        self.assertEqual(mapped['sso_organizational_unit'], '1ο Λύκειο Νέου Ψυχικού')

    def test_case_insensitive_attribute_names(self):
        attributes = {
            'EMPLOYEENUMBER': '99999',
            'GSNBRANCH': 'Διοικητικός',
            'OU': '2η Διεύθυνση Δευτεροβάθμιας Εκπαίδευσης',
        }
        mapped = _apply_cas_attribute_aliases(attributes.copy())
        self.assertEqual(mapped['employee_number'], '99999')
        self.assertEqual(mapped['gsn_branch'], 'Διοικητικός')
        self.assertEqual(mapped['sso_organizational_unit'], '2η Διεύθυνση Δευτεροβάθμιας Εκπαίδευσης')
