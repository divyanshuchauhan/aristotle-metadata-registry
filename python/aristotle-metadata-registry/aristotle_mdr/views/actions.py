from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, DetailView
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
import json

import reversion

from aristotle_mdr import perms
from aristotle_mdr import models as MDR
from aristotle_mdr.forms import actions
from aristotle_mdr.views.utils import generate_visibility_matrix
from aristotle_mdr.views import ReviewChangesView, display_review
from aristotle_mdr.forms.forms import ReviewChangesForm


class ItemSubpageView(object):
    def get_item(self):
        self.item = get_object_or_404(MDR._concept, pk=self.kwargs['iid']).item
        if not self.item.can_view(self.request.user):
            raise PermissionDenied
        return self.item

    def dispatch(self, *args, **kwargs):
        self.item = self.get_item()
        return super().dispatch(*args, **kwargs)


class ItemSubpageFormView(ItemSubpageView, FormView):
    def get_context_data(self, *args, **kwargs):
        kwargs = super().get_context_data(*args, **kwargs)
        kwargs['item'] = self.get_item()
        return kwargs


class SubmitForReviewView(ItemSubpageFormView):
    form_class = actions.RequestReviewForm
    template_name = "aristotle_mdr/actions/request_review.html"

    def get_context_data(self, *args, **kwargs):
        kwargs = super().get_context_data(*args, **kwargs)
        kwargs['reviews'] = self.get_item().review_requests.filter(status=MDR.REVIEW_STATES.submitted).all()
        kwargs['status_matrix'] = json.dumps(generate_visibility_matrix(self.request.user))
        return kwargs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        item = self.get_item()

        if form.is_valid():
            review = form.save(commit=False)
            review.requester = request.user
            review.save()
            review.concepts.add(item)
            message = mark_safe(
                _("<a href='{url}'>Review submitted, click to review</a>").format(url=reverse('aristotle_mdr:userReviewDetails', args=[review.pk]))
            )
            messages.add_message(request, messages.INFO, message)
            return HttpResponseRedirect(item.get_absolute_url())
        else:
            return self.form_invalid(form)


class ReviewActionMixin(object):
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        review = self.get_review()
        if not perms.user_can_view_review(self.request.user, review):
            raise PermissionDenied
        if review.status != MDR.REVIEW_STATES.submitted:
            return HttpResponseRedirect(reverse('aristotle_mdr:userReviewDetails', args=[review.pk]))
        return super().dispatch(*args, **kwargs)

    def get_review(self):
        self.review = get_object_or_404(MDR.ReviewRequest, pk=self.kwargs['review_id'])
        return self.review

    def get_context_data(self, *args, **kwargs):
        kwargs = super().get_context_data(*args, **kwargs)
        kwargs['review'] = self.get_review()
        return kwargs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class ReviewCancelView(ReviewActionMixin, FormView):
    form_class = actions.RequestReviewCancelForm
    template_name = "aristotle_mdr/user/user_request_cancel.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        review = self.get_review()
        if not self.request.user == review.requester:
            raise PermissionDenied
        if review.status != MDR.REVIEW_STATES.submitted:
            return HttpResponseRedirect(reverse('aristotle_mdr:userReviewDetails', args=[review.pk]))

        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_review()
        return kwargs

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.is_valid():
            review = form.save(commit=False)
            review.status = MDR.REVIEW_STATES.cancelled
            review.save()
            message = _("Review successfully cancelled")
            messages.add_message(request, messages.INFO, message)
            return HttpResponseRedirect(reverse('aristotle_mdr:userMyReviewRequests'))
        else:
            return self.form_invalid(form)


class ReviewRejectView(ReviewActionMixin, FormView):
    form_class = actions.RequestReviewRejectForm
    template_name = "aristotle_mdr/user/user_request_reject.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_review()
        return kwargs

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.status = MDR.REVIEW_STATES.rejected
            review.save()
            message = _("Review successfully rejected")
            messages.add_message(request, messages.INFO, message)
            return HttpResponseRedirect(reverse('aristotle_mdr:userReadyForReview'))
        else:
            return self.form_invalid(form)

class ReviewAcceptView(ReviewChangesView):

    form_list = [
        ('review_accept', actions.RequestReviewAcceptForm),
        ('review_changes', ReviewChangesForm)
    ]

    templates = {
        'review_accept': 'aristotle_mdr/user/user_request_accept.html',
        'review_changes': 'aristotle_mdr/helpers/wizard_form.html'
    }

    condition_dict = {'review_changes': display_review}
    display_review = None

    def dispatch(self, request, *args, **kwargs):

        review = self.get_review()
        if not perms.user_can_view_review(self.request.user, review):
            raise PermissionDenied
        if review.status != MDR.REVIEW_STATES.submitted:
            return HttpResponseRedirect(reverse('aristotle_mdr:userReviewDetails', args=[review.pk]))

        return super().dispatch(request, *args, **kwargs)

    def get_review(self):
        self.review = get_object_or_404(MDR.ReviewRequest, pk=self.kwargs['review_id'])
        return self.review

    def get_change_data(self):
        review = self.get_review()

        # Register status changes
        change_data = {
            'registrationAuthorities': [review.registration_authority],
            'state': review.state,
            'registrationDate': review.registration_date,
            'cascadeRegistration': review.cascade_registration,
            'changeDetails': review.message
        }

        return change_data

    def get_context_data(self, *args, **kwargs):
        kwargs = super().get_context_data(*args, **kwargs)
        kwargs['status_matrix'] = json.dumps(generate_visibility_matrix(self.request.user))
        kwargs['review'] = self.get_review()
        return kwargs

    def get_form_kwargs(self, step):
        self.items = self.get_review().concepts.all()
        kwargs = super().get_form_kwargs(step)

        if step == 'review_accept':
            return {'user': self.request.user}

        return kwargs

    def done(self, form_list, form_dict, **kwargs):
        review = self.get_review()

        self.items = review.concepts.all()
        message = self.register_changes_with_message(form_dict)

        # Update review object
        review.reviewer = self.request.user
        review.response = form_dict['review_accept'].cleaned_data['response']
        review.status = MDR.REVIEW_STATES.accepted
        review.save()

        messages.add_message(self.request, messages.INFO, message)

        return HttpResponseRedirect(reverse('aristotle_mdr:userReadyForReview'))


class CheckCascadedStates(ItemSubpageView, DetailView):
    pk_url_kwarg = 'iid'
    context_object_name = 'item'
    queryset = MDR._concept.objects.all()
    template_name = 'aristotle_mdr/actions/check_states.html'

    def dispatch(self, *args, **kwargs):
        self.item = self.get_item()
        if not self.item.item.registry_cascade_items:
            raise Http404
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        kwargs = super().get_context_data(*args, **kwargs)

        state_matrix = [
            # (item,[(states_ordered_alphabetically_by_ra_as_per_parent_item,state_of_parent_with_same_ra)],[extra statuses] )
            ]
        item = self.get_item()
        states = []
        ras = []
        for s in item.current_statuses():
            if s.registrationAuthority not in ras:
                ras.append(s.registrationAuthority)
                states.append(s)

        for i in item.item.registry_cascade_items:
            sub_states = [(None, None)] * len(ras)
            extras = []
            for s in i.current_statuses():
                ra = s.registrationAuthority
                if ra in ras:
                    sub_states[ras.index(ra)] = (s, states[ras.index(ra)])
                else:
                    extras.append(s)
            state_matrix.append((i, sub_states, extras))

        kwargs['known_states'] = states
        kwargs['state_matrix'] = state_matrix
        return kwargs
