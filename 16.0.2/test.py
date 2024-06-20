import argparse

parser = argparse.ArgumentParser()
parser.add_argument("table_name", metavar="table-name", help="blah", default=None)
parser.add_argument("--start-ts", help="blah2", default=None)
settings = parser.parse_args()
print(settings)
