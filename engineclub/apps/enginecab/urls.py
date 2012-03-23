from django.conf.urls.defaults import *


urlpatterns = patterns('enginecab.views',
    
    url(r'^$', 'users', name='cab'),
    url(r'^issues/$', 'issues', name='cab_issues'),
    url(r'^issues/(?P<object_id>\w+)/$', 'issue_detail', name='cab_issue_detail'),
    url(r'^lists/$', 'lists', name='cab_lists'),
    url(r'^lists/(?P<object_id>\w+)/$', 'list_detail', name='cab_list_detail'),
    url(r'^reindex/$', 'reindex', name='cab_reindex'),
    url(r'^resources/$', 'resources', name='cab_resources'),
    url(r'^users/$', 'users', name='cab_users'),
    url(r'^users/add/$', 'user_add', name='cab_user_add'),
    url(r'^users/(?P<object_id>\w+)/$', 'user_detail', name='cab_user_detail'),
    url(r'^users/(?P<object_id>\w+)/edit/$', 'user_edit', name='cab_user_edit'),

    (r'^invite/', include('invites.urls')),

    # url(r'^fix-resource-accounts/$', 'enginecab.views.fix_resource_accounts', name='cab-fix-resource-accounts'),
    # url(r'^one-off-util/$', 'enginecab.views.one_off_util', name='cab-one-off-util'),
    # url(r'^remove-dud-curations/$', 'enginecab.views.remove_dud_curations', name='remove-dud-curations'),
    # url(r'^show-curationless-resources/$', 'enginecab.views.show_curationless_resources', name='show-curationless-resources'),
    # url(r'^fix-curationless-resources/$', 'enginecab.views.fix_curationless_resources', name='fix-curationless-resources'),
    
)
