import tempfile, unittest
from pathlib import Path
import app

class CommunityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'test.db'; app.initialize(self.db)
    def tearDown(self): self.tmp.cleanup()
    def test_matches_opposite_kind_by_category_or_area(self):
        help_post=app.create_post({'kind':'help','title':'Need a lift','description':'To pantry','category':'Transport','area':'Northside'},self.db)
        app.create_post({'kind':'offer','title':'Ride available','description':'Can drive','category':'Transport','area':'East'},self.db)
        matches=app.find_matches(help_post['id'],self.db)
        self.assertTrue(any(m['kind']=='offer' and m['category']=='Transport' for m in matches))
        self.assertTrue(all(m['kind']=='offer' for m in matches))
    def test_invalid_posts_rejected(self):
        with self.assertRaises(ValueError): app.create_post({'kind':'help','title':'','description':'d','category':'c','area':'a'},self.db)
        with self.assertRaises(ValueError): app.create_post({'kind':'help','title':'x'*501,'description':'d','category':'c','area':'a'},self.db)
    def test_status_and_unknown_post(self):
        post=app.create_post({'kind':'offer','title':'Tools','description':'Borrow','category':'Supplies','area':'West'},self.db)
        self.assertEqual(app.set_status(post['id'],'resolved',self.db)['status'],'resolved')
        with self.assertRaises(ValueError): app.set_status(post['id'],'unsafe',self.db)
        with self.assertRaises(KeyError): app.set_status(9999,'open',self.db)
    def test_lists_demo_records_as_fictional_neighborhood_posts(self):
        self.assertGreaterEqual(len(app.list_posts(self.db)),4)

if __name__=='__main__': unittest.main()
