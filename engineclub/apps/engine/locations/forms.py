# forms.py

from bson.objectid import ObjectId
from django import forms

from analytics.shortcuts import increment_failed_locations
from ecutils.forms import DocumentForm, PlainForm
from resources.search import get_location

class LocationSearchForm(PlainForm):
    
    location = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}), label='Location', help_text='enter a post code or a place name', required=True)

    def __init__(self, *args, **kwargs):
        self.loc_found = None
        super(LocationSearchForm, self).__init__(*args, **kwargs)

    def clean(self):
        # if errors in data, cleaned_data may be wiped, and/or fields not available
        cleaned_data = self.cleaned_data
        data = cleaned_data.get('location', '').strip()
        self.loc_found = get_location(data)
        if not self.loc_found:
            increment_failed_locations(data)
            raise forms.ValidationError("Location not found.")
        return cleaned_data

class LocationEditForm(DocumentForm):
    # id = StringField(primary_key=True)
    postcode = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}), required=False)
    place_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    lat = forms.FloatField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    lon = forms.FloatField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    accuracy = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    loc_type = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    district = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    country_code = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-text expand'}))
    # edited = BooleanField(default=False)

    def clean(self):
        # if errors in data, cleaned_data may be wiped, and/or fields not available
        cleaned_data = self.cleaned_data
        cleaned_data['lat_lon'] = [cleaned_data.get('lat'), cleaned_data.get('lon')]
        postcode = cleaned_data['postcode']
        if postcode:
            cleaned_data['id'] = postcode.upper().replace(' ', '')
        else:
            cleaned_data['id'] = str(ObjectId())
            # remove this or mongo will create a postcode of ''
            del cleaned_data['postcode']
        cleaned_data['edited'] = True
        return cleaned_data
