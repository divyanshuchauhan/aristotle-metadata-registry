from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.forms import model_to_dict
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers, status, mixins, viewsets, generics
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.reverse import reverse

from reversion import revisions as reversion

from aristotle_mdr import models, perms
from aristotle_mdr.forms.search import PermissionSearchQuerySet
from ..serializers.base import Serializer, Deserializer, exclude_fields
from ..filters import concept_backend
from .. import permissions

from aristotle_mdr_api.token_auth.permissions import TokenPermissions

from ..views.utils import (
    DescriptionStubSerializerMixin,
    MultiSerializerViewSetMixin,
    ConceptResultsPagination,
    UUIDLookupModelMixin,
    api_excluded_fields,
    get_api_fields,
)


standard_fields = ('uuid', 'concept_type','visibility_status',)
class ConceptSerializerBase(serializers.ModelSerializer):
    concept_type = serializers.SerializerMethodField()
    visibility_status = serializers.SerializerMethodField()

    class Meta:
        model = models._concept
        fields = standard_fields
    def get_concept_type(self,instance):
        item = instance.item
        out = {"app":item._meta.app_label,'model':item._meta.model_name}
        return out
    def get_visibility_status(self,instance):
        out = {"public":instance.is_public(),'locked':instance.is_locked()}
        return out

class ConceptListSerializer(DescriptionStubSerializerMixin,ConceptSerializerBase):
    class Meta:
        model = models._concept
        fields = standard_fields + ('definition', 'name')

class ConceptDetailSerializer(ConceptSerializerBase):
    fields = serializers.SerializerMethodField('get_extra_fields')
    ids = serializers.SerializerMethodField('get_identifiers')
    slots = serializers.SerializerMethodField()
    links = serializers.SerializerMethodField()
    statuses = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pyserializer = Serializer()

    def get_serialized_object(self, instance):
        return self.pyserializer.serialize([instance.item], context=self.context)[0]

    class Meta:
        model = models._concept
        fields = standard_fields+('fields','statuses','ids','slots', 'links')

    def get_extra_fields(self, instance):
        return self.get_serialized_object(instance).get('fields',[])

    def get_identifiers(self, instance):
        return self.get_serialized_object(instance).get('identifiers',[])

    def get_slots(self, instance):
        return self.get_serialized_object(instance).get('slots', [])

    def get_links(self, instance):
        return self.get_serialized_object(instance).get('links', [])

    def get_statuses(self, instance):
        return self.get_serialized_object(instance).get('statuses',[])

class ConceptViewSet(
    MultiSerializerViewSetMixin,
    UUIDLookupModelMixin,
    #mixins.RetrieveModelMixin,
                    #mixins.UpdateModelMixin,

                    #viewsets.ModelViewSet):
    viewsets.ReadOnlyModelViewSet):
    """
    retrieve:
    Provides access to a specific metadata item.

    list:
    Provides access to a paginated list of metadata items.

    create:
    Create a new metadata item.
    """

    queryset = models._concept.objects.all()
    pagination_class = ConceptResultsPagination
    filter_backends = (concept_backend.ConceptFilterBackend,)
    filter_class = concept_backend.ConceptFilter

    permission_key = 'metadata'

    serializers = {
        'default': ConceptDetailSerializer,
        'list': ConceptListSerializer
    }


    def get_queryset(self):
        """
        Possible arguments include:

        type (string) : restricts to a particular concept type, eg. dataelement

        """
        self.queryset = self.get_content_type_for_request().objects.all()

        queryset = super(ConceptViewSet,self).get_queryset()
        if self.request:
            concepttype = self.request.query_params.get('type', None)
            locked = self.request.query_params.get('is_locked', None)
            public = self.request.query_params.get('is_public', None)
            queryset = queryset.visible(self.request.user)
        else:
            concepttype = None
            locked = None
            public = None
            queryset = queryset.public()

        #     # superseded_by_id = self.request.query_params.get('superseded_by', None)
        #     # if superseded_by_id is not None:
        #     #     queryset = queryset.filter(superseded_by=superseded_by_id)
        #     is_superseded = self.request.query_params.get('is_superseded', False)
        #     if is_superseded:
        #         queryset = queryset.filter(superseded_by__isnull=False)

        if locked is not None:
            locked = locked not in ["False","0","F"]
            queryset = queryset.filter(_is_locked=locked)
        if public is not None:
            public = public not in ["False","0","F"]
            queryset = queryset.filter(_is_public=public)

        return queryset

    def get_content_type_for_request(self):
        content_type = models._concept
        concepttype = self.request.query_params.get('type', None)

        if concepttype is not None:
            ct = concepttype.lower().split(":",1)
            if len(ct) == 2:
                app,model = ct
                content_type = ContentType.objects.get(app_label=app,model=model).model_class()
            else:
                model = concepttype
                content_type = ContentType.objects.get(model=model).model_class()

            class SpecialFilter(self.filter_class):
                class Meta(self.filter_class.Meta):
                    model = content_type

            self.filter_class = SpecialFilter

        return content_type

    def check_object_permissions(self, request, obj):
        item = obj.item
        if not perms.user_can_view(request.user, item):
            raise PermissionDenied
        else:
            return obj

    def get_object(self):
        item = super(ConceptViewSet,self).get_object().item
        if not perms.user_can_view(self.request.user, item):
            raise PermissionDenied
        else:
            return item
