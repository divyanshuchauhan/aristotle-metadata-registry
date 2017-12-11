from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.utils import six

from aristotle_mdr import models, perms
from dal import autocomplete


class GenericAutocomplete(autocomplete.Select2QuerySetView):
    model = None
    template_name = "autocomplete_light/item.html"

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get('app_name', None) and kwargs.get('model_name', None):
            self.model = get_object_or_404(
                ContentType, app_label=kwargs['app_name'], model=kwargs['model_name']
            ).model_class()
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated():
            return self.model.objects.none()

        qs = self.model.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs

    def get_result_title(self, result):
        """Return the title of a result."""
        return six.text_type(result)

    def get_result_text(self, result):
        """Return the label of a result."""

        template = get_template(self.template_name)
        # context = {"result": result, 'request': self.request}
        context = Context({"result": result, 'request': self.request})
        return template.render(context)

    def get_results(self, context):
        """Return data for the 'results' key of the response."""
        return [
            {
                'id': self.get_result_value(result),
                'title': self.get_result_title(result),
                'text': self.get_result_text(result),
            } for result in context['object_list']
        ]


class GenericConceptAutocomplete(GenericAutocomplete):
    model = models._concept
    template_name = "autocomplete_light/concept.html"

    def get_queryset(self):
        if not self.request.user.is_authenticated():
            qs = self.model.objects.public()
        else:
            qs = self.model.objects.visible(self.request.user)

        if self.q:
            q = Q(name__icontains=self.q)
            q |= Q(uuid__iexact=self.q)
            if 'aristotle_mdr.contrib.identifiers' in settings.INSTALLED_APPS:
                q |= Q(identifiers__identifier__iexact=self.q)
            try:
                int(self.q)
                q |= Q(pk=self.q)
            except:
                pass
            qs = qs.filter(q)
        return qs

    def get_results(self, context):
        """Return data for the 'results' key of the response."""
        return [
            {
                'id': self.get_result_value(result),
                'uuid': str(result.uuid),
                'title': self.get_result_title(result),
                'text': self.get_result_text(result),
            } for result in context['object_list']
        ]


class UserAutocomplete(GenericAutocomplete):
    # model = User
    model = None
    template_name = "aristotle_mdr/actions/autocompleteUser.html"

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        self.model = get_user_model()

        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated():
            raise PermissionDenied

        if not perms.user_can_query_user_list(self.request.user):
            raise PermissionDenied

        if self.q:
            qs = self.model.objects.filter(is_active=True).filter(
                Q(username__icontains=self.q) |
                Q(email__icontains=self.q) |
                Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
            )
        else:
            if self.request.user.is_superuser:
                qs = self.model.objects.filter(is_active=True)
            else:
                qs = self.model.objects.none()

        return qs

    def get_result_text(self, result):
        """Return the label of a result."""

        template = get_template(self.template_name)
        result.highlight = {}
        for f in ['username', 'email', 'get_full_name']:
            field = getattr(result, f, None)
            if callable(field):
                field = field()
            if field and self.q.lower() in field.lower():
                index = field.lower().index(self.q.lower())
                offset = index + len(self.q)
                field = "%s<b><u>%s</u></b>%s" % (field[:index], field[index:offset], field[offset:])

            result.highlight[f] = field
        context = Context({"result": result, 'request': self.request})
        return template.render(context)

    def get_result_title(self, result):
        """Return the title of a result."""
        return six.text_type(result)
