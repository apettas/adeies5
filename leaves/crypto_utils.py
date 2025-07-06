"""
Κρυπτογραφικές λειτουργίες για ασφαλή διαχείριση αρχείων
Security by Design - AES-256 encryption
"""
import os
import hashlib
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from django.conf import settings


class SecureFileHandler:
    """Χειρισμός κρυπτογραφημένων αρχείων"""
    
    CHUNK_SIZE = 64 * 1024  # 64KB chunks για μεγάλα αρχεία
    
    @staticmethod
    def generate_key():
        """Δημιουργία τυχαίου AES-256 κλειδιού"""
        return get_random_bytes(32)  # 256 bits = 32 bytes
    
    @staticmethod
    def encrypt_file(file_content, key=None):
        """
        Κρυπτογράφηση περιεχομένου αρχείου με AES-256-CBC
        
        Args:
            file_content (bytes): Το περιεχόμενο του αρχείου
            key (bytes, optional): Κλειδί κρυπτογράφησης. Αν δεν δοθεί, δημιουργείται νέο.
        
        Returns:
            tuple: (encrypted_content, key_hex)
        """
        if key is None:
            key = SecureFileHandler.generate_key()
        
        # Δημιουργία τυχαίου IV
        iv = get_random_bytes(AES.block_size)
        
        # Δημιουργία cipher object
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Padding του περιεχομένου σε μπλοκ των 16 bytes
        padded_content = pad(file_content, AES.block_size)
        
        # Κρυπτογράφηση
        encrypted_content = cipher.encrypt(padded_content)
        
        # Συνδυασμός IV + encrypted_content
        final_content = iv + encrypted_content
        
        return final_content, key.hex()
    
    @staticmethod
    def decrypt_file(encrypted_content, key_hex):
        """
        Αποκρυπτογράφηση περιεχομένου αρχείου
        
        Args:
            encrypted_content (bytes): Κρυπτογραφημένο περιεχόμενο (IV + data)
            key_hex (str): Κλειδί σε hex format
        
        Returns:
            bytes: Αποκρυπτογραφημένο περιεχόμενο
        """
        # Μετατροπή κλειδιού από hex
        key = bytes.fromhex(key_hex)
        
        # Εξαγωγή IV (πρώτα 16 bytes)
        iv = encrypted_content[:AES.block_size]
        
        # Εξαγωγή κρυπτογραφημένων δεδομένων
        ciphertext = encrypted_content[AES.block_size:]
        
        # Δημιουργία cipher object
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Αποκρυπτογράφηση
        padded_content = cipher.decrypt(ciphertext)
        
        # Αφαίρεση padding
        original_content = unpad(padded_content, AES.block_size)
        
        return original_content
    
    @staticmethod
    def save_encrypted_file(file_obj, file_path):
        """
        Αποθήκευση κρυπτογραφημένου αρχείου στον δίσκο
        
        Args:
            file_obj: Django UploadedFile object
            file_path (str): Πλήρη διαδρομή αποθήκευσης
        
        Returns:
            tuple: (success, key_hex, file_size)
        """
        try:
            # Δημιουργία καταλόγου αν δεν υπάρχει
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Διάβασμα περιεχομένου αρχείου
            file_content = file_obj.read()
            file_size = len(file_content)
            
            # Κρυπτογράφηση
            encrypted_content, key_hex = SecureFileHandler.encrypt_file(file_content)
            
            # Αποθήκευση κρυπτογραφημένου αρχείου
            with open(file_path, 'wb') as f:
                f.write(encrypted_content)
            
            return True, key_hex, file_size
            
        except Exception as e:
            print(f"Error saving encrypted file: {e}")
            return False, None, 0
    
    @staticmethod
    def save_encrypted_bytes(file_content, file_path):
        """
        Αποθήκευση κρυπτογραφημένου αρχείου από bytes content
        
        Args:
            file_content (bytes): Περιεχόμενο αρχείου σε bytes
            file_path (str): Πλήρη διαδρομή αποθήκευσης
        
        Returns:
            tuple: (file_path, key_hex)
        """
        try:
            # Δημιουργία καταλόγου αν δεν υπάρχει
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Κρυπτογράφηση
            encrypted_content, key_hex = SecureFileHandler.encrypt_file(file_content)
            
            # Αποθήκευση κρυπτογραφημένου αρχείου
            with open(file_path, 'wb') as f:
                f.write(encrypted_content)
            
            return file_path, key_hex
            
        except Exception as e:
            # Log του σφάλματος
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving encrypted file: {str(e)}")
            
            raise e
        try:
            # Δημιουργία καταλόγου αν δεν υπάρχει
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Ανάγνωση περιεχομένου αρχείου
            file_obj.seek(0)
            file_content = file_obj.read()
            
            # Κρυπτογράφηση
            encrypted_content, key_hex = SecureFileHandler.encrypt_file(file_content)
            
            # Αποθήκευση κρυπτογραφημένου αρχείου
            with open(file_path, 'wb') as f:
                f.write(encrypted_content)
            
            # Ασφαλής διαγραφή του original content από μνήμη
            del file_content
            
            return True, key_hex, len(encrypted_content)
            
        except Exception as e:
            # Log του σφάλματος (χωρίς sensitive δεδομένα)
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving encrypted file: {str(e)}")
            
            return False, None, 0
    
    @staticmethod
    def load_encrypted_file(file_path, key_hex):
        """
        Φόρτωση και αποκρυπτογράφηση αρχείου από τον δίσκο
        
        Args:
            file_path (str): Διαδρομή κρυπτογραφημένου αρχείου
            key_hex (str): Κλειδί κρυπτογράφησης σε hex format
        
        Returns:
            bytes or None: Αποκρυπτογραφημένο περιεχόμενο ή None σε περίπτωση σφάλματος
        """
        try:
            # Έλεγχος ύπαρξης αρχείου
            if not os.path.exists(file_path):
                return None
            
            # Ανάγνωση κρυπτογραφημένου αρχείου
            with open(file_path, 'rb') as f:
                encrypted_content = f.read()
            
            # Αποκρυπτογράφηση
            decrypted_content = SecureFileHandler.decrypt_file(encrypted_content, key_hex)
            
            return decrypted_content
            
        except Exception as e:
            # Log του σφάλματος
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading encrypted file: {str(e)}")
            
            return None
    
    @staticmethod
    def delete_encrypted_file(file_path):
        """
        Ασφαλής διαγραφή κρυπτογραφημένου αρχείου
        
        Args:
            file_path (str): Διαδρομή αρχείου για διαγραφή
        
        Returns:
            bool: True αν διαγράφηκε επιτυχώς
        """
        try:
            if os.path.exists(file_path):
                # Ασφαλής διαγραφή με overwrite (optional, για extra security)
                with open(file_path, 'r+b') as f:
                    length = f.seek(0, 2)  # Μετάβαση στο τέλος
                    f.seek(0)
                    f.write(os.urandom(length))  # Overwrite με random data
                    f.flush()
                
                # Διαγραφή αρχείου
                os.remove(file_path)
                
                return True
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting encrypted file: {str(e)}")
            
        return False
    
    @staticmethod
    def validate_file(file_obj):
        """
        Επικύρωση αρχείου (τύπος, μέγεθος)
        
        Args:
            file_obj: Django UploadedFile object
        
        Returns:
            tuple: (is_valid, error_message)
        """
        from .models import SecureFile
        
        # Έλεγχος μεγέθους
        if file_obj.size > SecureFile.MAX_FILE_SIZE:
            size_mb = SecureFile.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"Το αρχείο είναι πολύ μεγάλο. Μέγιστο μέγεθος: {size_mb}MB"
        
        # Έλεγχος επέκτασης
        filename = file_obj.name.lower()
        extension = filename.split('.')[-1] if '.' in filename else ''
        
        if extension not in SecureFile.ALLOWED_EXTENSIONS:
            allowed = ', '.join(SecureFile.ALLOWED_EXTENSIONS).upper()
            return False, f"Μη επιτρεπτός τύπος αρχείου. Επιτρεπτοί τύποι: {allowed}"
        
        # Έλεγχος content type (basic)
        content_type = file_obj.content_type or ''
        allowed_content_types = [
            'application/pdf',
            'image/jpeg',
            'image/jpg', 
            'image/png'
        ]
        
        if content_type not in allowed_content_types:
            return False, "Μη επιτρεπτός τύπος περιεχομένου αρχείου"
        
        return True, ""
    
    @staticmethod
    def get_content_type(filename):
        """
        Προσδιορισμός Content-Type βάσει επέκτασης
        
        Args:
            filename (str): Όνομα αρχείου
        
        Returns:
            str: Content-Type
        """
        extension = filename.lower().split('.')[-1]
        
        content_types = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png'
        }
        
        return content_types.get(extension, 'application/octet-stream')


class FileAccessController:
    """Έλεγχος πρόσβασης σε αρχεία"""
    
    @staticmethod
    def can_user_access_file(user, secure_file):
        """
        Ελέγχει αν ο χρήστης έχει δικαίωμα πρόσβασης στο αρχείο
        
        Args:
            user: User object
            secure_file: SecureFile object
        
        Returns:
            bool: True αν έχει δικαίωμα πρόσβασης
        """
        # Ο χρήστης που ανέβασε το αρχείο έχει πάντα πρόσβαση
        if secure_file.uploaded_by == user:
            return True
        
        # Ο ιδιοκτήτης της αίτησης έχει πρόσβαση
        if secure_file.leave_request.user == user:
            return True
        
        # Προϊστάμενος του τμήματος έχει πρόσβαση
        if (user.is_department_manager and 
            secure_file.leave_request.user.department == user.department):
            return True
        
        # Χειριστής αδειών έχει πρόσβαση σε όλα
        if user.is_leave_handler:
            return True
        
        return False
    
    @staticmethod
    def log_file_access(user, secure_file, success=True):
        """
        Καταγραφή προσπάθειας πρόσβασης σε αρχείο
        
        Args:
            user: User object
            secure_file: SecureFile object  
            success (bool): Αν η πρόσβαση ήταν επιτυχής
        """
        import logging
        logger = logging.getLogger('file_access')
        
        log_data = {
            'user_id': user.id,
            'username': user.username,
            'file_id': secure_file.id,
            'filename': secure_file.original_filename,
            'leave_request_id': secure_file.leave_request.id,
            'success': success,
            'ip_address': None  # Θα συμπληρωθεί από την view
        }
        
        if success:
            logger.info(f"File access granted: {log_data}")
        else:
            logger.warning(f"File access denied: {log_data}")