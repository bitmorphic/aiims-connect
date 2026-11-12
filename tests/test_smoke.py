import unittest
from pathlib import Path
class Smoke(unittest.TestCase):
 def test_schema_has_15_entities(self):
  p=Path(__file__).resolve().parents[1]/'sql'/'schema.sql';self.assertEqual(p.read_text().lower().count('create table if not exists'),15)
 def test_env_example(self):self.assertTrue((Path(__file__).resolve().parents[1]/'.env.example').exists())
if __name__=='__main__':unittest.main()
