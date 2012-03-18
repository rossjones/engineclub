from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from pymongo.objectid import ObjectId

from accounts.models import get_account
from ecutils.utils import get_one_or_404
from issues.models import Issue


@login_required
def issue_list(request, template_name='youraliss/issues.html'):

    account = get_account(request.user.id)
    issues = Issue.objects.for_account(account)
    template_context = {'objects': issues}
    return render_to_response(template_name, RequestContext(request, template_context))

@login_required
def issue_detail(request, object_id, template_name='youraliss/issue_detail.html'):

    account = get_account(request.user.id)
    issue = get_one_or_404(Issue, id=ObjectId(object_id))

    # issue = Issue.objects.get_or_404(id=issue_id,
    #     account=account)

    # if not issue.opened:
    #     alert.mark_read()

    if request.method == 'POST' and 'resolved' in request.POST:
        # alert.resolve()
        return HttpResponseRedirect(reverse('issue_list'))

    return render_to_response('issues/issue_detail.html', {
        'account': account,
        'issue': issue,
    }, RequestContext(request))
    return render_to_response(template_name, RequestContext(request, template_context))
