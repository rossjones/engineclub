# from django.db import models

from django.conf import settings

from mongoengine import *
from mongoengine.connection import _get_db as get_db
from datetime import datetime

from pymongo import Connection, DESCENDING, ASCENDING, GEO2D
from pysolr import Solr
import re

from ecutils.utils import minmax
from accounts.models import Account, get_account

from copy import deepcopy

COLL_STATUS_NEW = 'new'
COLL_STATUS_LOC_CONF = 'location_confirm'
COLL_STATUS_TAGS_CONF = 'tags_confirm'
COLL_STATUS_ = ''
COLL_STATUS_COMPLETE = 'complete'

STATUS_OK = 'OK'
STATUS_BAD = 'BAD'

POSTCODE = 'POSTCODE'
POSTCODEDISTRICT = 'POSTCODEDISTRICT'
OSM_PLACENAME = 'OSM_PLACENAME'
GOOGLE_PLACENAME = 'GOOGLE_PLACENAME'

import logging
logger = logging.getLogger('aliss')

class ItemMetadata(EmbeddedDocument):
    last_modified = DateTimeField(default=datetime.now)
    author = ReferenceField(Account)
    shelflife = DateTimeField(default=datetime.now) # TODO set to now + settings.DEFAULT_SHELFLIFE
    status = StringField()
    note = StringField()

    def update(self, author, last_modified=None):
        """docstring for update"""
        self.author = author
        self.last_modified = last_modified or datetime.now()

class CalendarEvent(EmbeddedDocument):
    """used to add event data to Resource. Subset of W3C Calendar API: http://www.w3.org/TR/calendar-api/"""
    start = DateTimeField()
    end = DateTimeField()
    status = StringField(default='confirmed') # 'provisional', 'confirmed', 'cancelled'.
    # recurrence = EmbeddedDocumentField(CalendarRepeatRule)

class Location(Document):
    """Location document, based on combined data sources, geonames + OSM
    loc_type = POSTCODE | POSTCODEDISTRICT | OSM_PLACENAME | GOOGLE_PLACENAME

    """
    id = StringField(primary_key=True)
    postcode = StringField()
    place_name = StringField(required=True)
    lat_lon = GeoPointField(required=True)
    loc_type = StringField(required=True)
    accuracy = IntField()
    district = StringField()
    country_code = StringField()

    meta = {
        'indexes': [('place_name', 'country_code', '-accuracy')],
        'allow_inheritance': False,
        'collection': 'location'
    }
    def __unicode__(self):
        return ', '.join([self.postcode, self.place_name]) \
            if self.postcode \
            else ', '.join([self.place_name, self.district])

    @classmethod
    def create_from(cls, name):
        result = None
        C = { 'England': 'ENG', 'Scotland': 'SCT', 'Wales': 'WAL', 'other': None}
        res, addr = lookup_postcode(name)
        if addr:
            attrs = {
                'place_name': addr.get('locality', ''),
                'lat_lon': (res.geometry.location.lat, res.geometry.location.lng),
                'accuracy': 6,
                'district': addr.get('administrative_area_level_2', ''),
            }
            pc = addr.get('postal_code')
            if pc:
                attrs['postcode'] = pc
                attrs['loc_type'] = POSTCODE if len(pc) > 4 else POSTCODEDISTRICT
                attrs['id'] = pc.upper().replace(' ', '')
            else:
                attrs['loc_type'] = GOOGLE_PLACENAME
                attrs['id'] = '%s_%s' % (attrs['place_name'], attrs['district'])
            attrs['country_code'] = C.get(addr.get('administrative_area_level_1', 'other')) or addr.get('country')

            result = Location(**attrs)
            result.save()
        return result

def lookup_postcode(pc):
    from googlegeocoder import GoogleGeocoder
    geocoder = GoogleGeocoder()

    try:
        search = geocoder.get(pc, region='UK')
    except ValueError:
        return None, None
    res, addr = _make_addr(search)
    return res, addr

def _make_addr(results):

    for res in results:
        addr = {}
        for c in res.address_components:
            try:
                addr[c.__dict__['types'][0]] = c.long_name
            except IndexError:
                pass
            pc = (addr.get('postal_code') or addr.get('postal_code_prefix', '')).split()
        # if len(pc) > 1 and len(pc[1]) == 3: # full pc
        if pc: # any pc
            addr['postal_code'] = ' '.join(pc)
            break
    return res, addr

class Moderation(EmbeddedDocument):
    outcome = StringField()
    note = StringField()
    owner = ReferenceField(Account)
    item_metadata = EmbeddedDocumentField(ItemMetadata,default=ItemMetadata)

class Curation(Document):
    outcome = StringField()
    tags = ListField(StringField(max_length=96), default=list)
    # rating - not used
    note = StringField()
    data = DictField()
    resource = ReferenceField('Resource')
    owner = ReferenceField(Account)
    item_metadata = EmbeddedDocumentField(ItemMetadata,default=ItemMetadata)

    def perm_can_edit(self, user):
        """docstring for perm_can_edit"""
        acct = get_account(user.id)
        return self.owner == acct

    def perm_can_delete(self, user):
        """docstring for perm_can_edit"""
        acct = get_account(user.id)
        return self.owner == acct

class Resource(Document):
    """ Main model for ALISS resource """
    title = StringField(required=True)
    description = StringField(default='')
    resource_type = StringField()
    uri = StringField()
    locations = ListField(ReferenceField(Location), default=list)
    tmp_locations = ListField(StringField(max_length=16), default=list)
    service_area = ListField(ReferenceField(Location), default=list)
    calendar_event = EmbeddedDocumentField(CalendarEvent)
    moderations = ListField(EmbeddedDocumentField(Moderation), default=list)
    curations = ListField(ReferenceField(Curation), default=list)
    tags = ListField(StringField(max_length=96), default=list)
    related_resources = ListField(ReferenceField('RelatedResource'))
    owner = ReferenceField(Account, required=True)
    item_metadata = EmbeddedDocumentField(ItemMetadata,default=ItemMetadata)

    @classmethod
    def reindex_for(cls, acct):
        for c in Curation.objects(owner=acct):
            c.resource.reindex()

    def save(self, *args, **kwargs):
        reindex = kwargs.pop('reindex', False)
        author = kwargs.pop('author', None)
        created = self.id is None
        super(Resource, self).save(*args, **kwargs)
        self.item_metadata.update(author or self.owner)
        if created:
            if not self.moderations:
                obj = Moderation(outcome=STATUS_OK, owner=self.owner)
                obj.item_metadata.author = self.owner
                self.moderations.append(obj)
            if not self.curations:
                obj = Curation(outcome=STATUS_OK, tags=self.tags, owner=self.owner)
                obj.item_metadata.author = self.owner
                obj.resource = self
                obj.save()
                self.curations.append(obj)
            super(Resource, self).save(*args, **kwargs)

        if reindex:
            self.reindex()

    def delete(self, *args, **kwargs):
        """docstring for delete"""
        for c in self.curations:
            c.delete()
        self.reindex(remove=True)
        super(Resource, self).delete(*args, **kwargs)

    def _all_tags(self):
        tags = self.tags
        for c in self.curations:
            tags.extend(c.tags)
        return list(set(tags))
    all_tags = property(_all_tags)

    def get_curation_for_acct(self, account):
        # check if user already has a curation for this resource
        if account:
            for index, obj in enumerate(self.curations):
                if obj.owner.id == account.id:
                    return index, obj
        return None, None

    def get_moderation_for_acct(self, account):
        # check if user already has a moderation for this resource
        if account:
            for index, obj in enumerate(self.moderations):
                if obj.owner.id == account.id:
                    return index, obj
        return None, None

    def reindex(self, remove=False):
        """docstring for reindex"""
        conn = Solr(settings.SOLR_URL)
        # needs wildcard to remove indexing for multiple locations: <id>_<n>
        conn.delete(q='id:%s*' % self.id)
        if not remove:
            self.index(conn)

    def index(self, conn=None):
        """conn is Solr connection"""
        tags = list(self.tags)
        accounts = []
        collections = []
        description = [self.description]

        # try:

        for obj in self.curations:
            tags.extend(obj.tags)
            accounts.append(unicode(obj.owner.id))
            if hasattr(obj.owner, 'collections'):
                collections.extend(obj.owner.collections)
            description.extend([obj.note or u'', unicode(obj.data) or u''])

        # except AttributeError:
        #     logger.error("fixed error in curations while indexing resource: %s, %s" % (self.id, self.title))
        #     self.curations = []
        #     self.save()
        doc = {
            'id': unicode(self.id),
            'res_id': unicode(self.id),
            'title': self.title,
            'short_description': self.description,
            'description': u'\n'.join(description),
            'keywords': u', '.join(list(set(tags))),
            'accounts': u', '.join(accounts),
            'collections': u', '.join(set([str(c.id) for c in collections])),
            'uri': self.uri,
            'loc_labels': [] # [', '.join([loc.label, loc.place_name]) for loc in self.locations]
        }
        if self.calendar_event:
            doc['event_start'] = self.calendar_event.start #.date()
            if self.calendar_event.end:
                doc['event_end'] = self.calendar_event.end #.date()
        result = []
        if self.locations:
            for i, loc in enumerate(self.locations):
                loc_doc = deepcopy(doc)
                loc_doc['id'] = u'%s_%s' % (unicode(self.id), i)
                loc_doc['pt_location'] = [lat_lon_to_str(loc)]
                loc_doc['loc_labels'] = [unicode(loc)]
                result.append(loc_doc)
        else:
            result = [doc]

        if conn:
            conn.add(result)
        return result

    def perm_can_edit(self, user):
        """docstring for perm_can_edit"""
        acct = get_account(user.id)
        return self.owner == acct

    def perm_can_delete(self, user):
        """docstring for perm_can_edit"""
        acct = get_account(user.id)
        return self.owner == acct

class RelatedResource(Document):
    """docstring for RelatedResource"""
    source = ReferenceField(Resource)
    target = ReferenceField(Resource)
    rel_type = StringField()
    item_metadata = EmbeddedDocumentField(ItemMetadata,default=ItemMetadata)


def load_resource_data(document, resource_data):
    new_data = eval(resource_data.read())
    db = get_db()
    db[document].insert(new_data)
    return db

###############################################################
# LOCATION STUFF - PUBLIC

def get_location(namestr, dbname=settings.MONGO_DATABASE_NAME, just_one=True, starts_with=False):

    db = get_db()
    coll = db.location
    if len(namestr) > 2 and namestr[2].isdigit():
        name = namestr.upper().replace(' ', '').strip()
        field = '_id'
    else:
        name = namestr.capitalize().strip()
        field = 'place_name'
        coll.ensure_index([
            ('place_name', ASCENDING),
            ('country_code', ASCENDING),
            ('accuracy', DESCENDING)
            ])

    if starts_with:
        name = re.compile('^%s' % name, re.IGNORECASE)
    result = coll.find_one({field: name}) if just_one else coll.find({field: name}).limit(20)
    if result and (type(result) == dict or result.count() > 0):

        return result
    else:
        return []

def lat_lon_to_str(loc):
    """docstring for lat_lon_to_str"""
    if loc:
        if type(loc) == Location:
            return (settings.LATLON_SEP).join([unicode(loc.lat_lon[0]), unicode(loc.lat_lon[1])])
        return (settings.LATLON_SEP).join([unicode(loc[0]), unicode(loc[1])])
    else:
        return ''


###############################################################
# SEARCH STUFF

def _make_fq(event, accounts, collections):
    fq = []
    if event:
        fq.append('(event_start:[NOW/DAY TO *] OR event_end:[NOW/DAY TO *])')
    if accounts:
        fq.append('accounts:(%s)'% ' OR '.join(accounts))
    if collections:
        fq.append('collections:(%s)'% ' OR '.join(collections))
    if fq:
        return ' AND '.join(fq)
    return None


def find_by_place(name, kwords, loc_boost=None, start=0, max=None, accounts=None, collections=None, event=None):
    loc = get_location(name)
    if loc:
        kw = {
            'start': start,
            'rows': minmax(0, settings.SOLR_ROWS, max, settings.SOLR_ROWS),
            'fl': '*,score',
            # 'fq': 'accounts:(4d9c3ced89cb162e5e000000 OR 4d9b99d889cb16665c000000) ',
            'qt': 'resources',
            'sfield': 'pt_location',
            'pt': lat_lon_to_str(loc['lat_lon']),
            'bf': 'recip(geodist(),2,200,20)^%s' % (loc_boost or settings.SOLR_LOC_BOOST_DEFAULT),
            'sort': 'score desc',
        }
        fq =  _make_fq(event, accounts, collections)
        if fq:
            kw['fq'] = fq

        conn = Solr(settings.SOLR_URL)
        return loc['lat_lon'], conn.search(kwords.strip() if kwords else '', **kw)
    else:
        return None, None

def find_by_place_or_kwords(name, kwords, loc_boost=None, start=0, max=None, accounts=None, collections=None, event=None):
    """docstring for find_by_place_or_kwords"""
    if name:
        return find_by_place(name, kwords, loc_boost, start, max, accounts, collections, event)
    # keywords only
    kw = {
        'start': start,
        'rows': minmax(0, settings.SOLR_ROWS, max, settings.SOLR_ROWS),
        'fl': '*,score',
        'qt': 'resources',
    }
    fq =  _make_fq(event, accounts, collections)
    # example 'fq': '(event_start:[NOW/DAY TO *] OR event_end:[NOW/DAY TO *]) AND accounts:4d9b99d889cb16665c000000'
    if fq:
        kw['fq'] = fq

    conn = Solr(settings.SOLR_URL)
    return None, conn.search(kwords.strip() if kwords else '', **kw)
