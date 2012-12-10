import sys, os
import codecs
import csv
import bleach
import tempfile
from resources.models import Resource, RelatedResource
from accounts.models import Account
from locations.models import Location
from resources.search import get_location

LIMIT = 2000
DELIM = ','
WWW = 'url'
TITLE = 'title'
DESCRIPTION = 'description'
TAGS = 'tags'
POSTCODE = 'locations'

CORE_LABELS = [WWW, TITLE, DESCRIPTION, TAGS, POSTCODE]

def handle_uploaded_file(request, f):
    """
    For now we assume the uploaded CSV or Excel has the following fields
    which we will use to create resources.

        url,title,description,tags,locations
    """
    _,filename = tempfile.mkstemp()

    with open(filename, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

    importer = Importer('aliss', request.user.id)
    try:
        (updated, duplicates,) = importer.import_from(filename)
    finally:
        importer.teardown()

SEP = '============\n'

class Importer(object):
    """docstring for Importer"""

    def __init__(self, db_name, user_id):
        super(Importer, self).__init__()
        self.db_name = db_name
        self.account = Account.objects.get(local_id=str(user_id))
        self._setup()

    def _db_info(self):
        print SEP
        print 'connection: ' + self.db_name
        print 'resource: %s' % Resource.objects.count()
        print 'acct resource: %s' % Resource.objects(owner=self.account).count()
        print 'related resources: %s' % RelatedResource.objects.count()
        print 'locations: %s' % Location.objects.count()
        print SEP

    def _setup(self):
        self._db_info()

    def teardown(self):
        # conn = Connection(host=settings.MONGO_HOST, port=settings.MONGO_PORT)
        # conn.drop_database(db_name)
        # Resource.objects(owner=account).delete(safe=True)
        # Location.drop_collection()
        self._db_info()

    def get_dict_from_row(self, row, encoding='UTF-8'):
        """docstring for get_dict_from_row(labels, r)"""
        result = {}
        empty = True
        for ix, field in enumerate(row):
            result[self.labels[ix]] = unicode(field, encoding).strip()
            if field:
                empty = False
        return None if empty else result

    def import_from(self, fname, limit= LIMIT, encoding='UTF-8'):
        """ """
        result = {}
        self.labels = None
        f = codecs.open(fname, 'rt')
        row = 0
        updated, dupes = 0, 0
        try:
            reader = csv.reader(f, delimiter=DELIM)
            for r in reader:
                if row == 0:
                    self.labels = r
                    row += 1
                else:
                    item_dict = self.get_dict_from_row(r)
                    if item_dict:
                        item = self.make_item(item_dict, row)
                        if item:
                            updated = updated + 1
                        else:
                            dupes = dupes + 1

                        print SEP
                        # print row, item.title #, item.url
                        if item_dict[POSTCODE]:
                            pass
                            print item_dict[POSTCODE]
                        else:
                            pass
                            print '**** no postcode ***', item_dict[POSTCODE]

                        for o in item.locations:
                            print '- loc', o

                        row += 1
                if row > limit:
                    break

        finally:
            f.close()

        return updated, dupes


    def make_description(self, item_dict):
        """docstring for make_address"""
        return item_dict[DESCRIPTION]

        # return '%s, %s, %s, %s, %s, %s, Scotland, GB' % (
        # # return '%s, GB' % (
        #     item_dict[POSTCODE],
        #     item_dict[STREET],
        #     item_dict[ADDRESS2],
        #     item_dict[ADDRESS3],
        #     item_dict[CITY],
        #     item_dict[COUNTY],
        #     )


    def get_postcode_data(self, postcode):
        """docstring for get_postcode_data"""
        # from firebox.ordnancesurvey import get_os_postcode, OS_LABEL, OS_TYPE, OS_LAT, OS_LON, OS_WARD, OS_DISTRICT, OS_COUNTRY

        result = None
        if postcode == '':
            return result
        try:
            location = get_location(postcode, create_location=True)
            # print location
            if location:
                result = Location.objects.get(id=location['_id'])
                # [Location.objects.get(id=loc['_id']) for loc in locations]
            # print 'already got:', postcode
        except Location.DoesNotExist:
            print 'not found- ', postcode
            # print Location.create_from(postcode)

        return result

    def make_item(self, item_dict, row):
        """
            Creates a new resource item, and returns it.  We should return None if the item
            already exists, although how we determine that isn't 100% clear at present.  This
            is just ready for the next batch of work.
        """
        def _fix_url(url):
            return 'http://%s' % url if url and not url.startswith('http://') else url

        locations = [self.get_postcode_data(pc.strip()) for pc in item_dict[POSTCODE].split(',')]
        locations = [loc for loc in locations if loc]
        data =  {
            'title': item_dict[TITLE],
            'owner': self.account,
            'tags': [i.lower() for i in item_dict[TAGS].split(', ') if i != 'ICT'],
            'description': self.make_description(item_dict),
            'uri': _fix_url(item_dict[WWW]),
            'locations': locations
            }
        item =  Resource.objects.create(**data)
        return item




