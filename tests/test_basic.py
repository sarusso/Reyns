
import unittest


#----------------------
# Logging
#----------------------

# Enable only critical logging in unit tests by default
#logging.basicConfig(level=logging.CRITICAL) 
#logger = logging.getLogger("dockerops")


#----------------------
# Tests
#----------------------

class test_basic(unittest.TestCase):

    def setUp(self):       
        pass


    def test_args(self):
 
        self.assertEqual('2', '2')

        
    def tearDown(self):
        pass


